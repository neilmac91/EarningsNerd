"""Voice gate for backend copy that reaches users (docs/brand/07-voice.md; CLAUDE.md rule 12; D-036).

The frontend copy gates (no-em-dash-copy.spec.ts, brandCopyRules.spec.ts) never read Python, yet the
backend writes words people read verbatim: HTTP details that lib/api/client.ts hands to toasts and
inline errors, the waitlist join message WaitlistForm renders as its heading, stream errors, mail,
PDF, CSV and workbook text. This AST walk reads those literals (f-string parts included) in
app/routers, app/services, app/dependencies.py and main.py, and fails on a break that a file outside
EXEMPT ships.

A literal reaches a user when it is:

1. the value of a COPY_KEYWORDS keyword (``HTTPException(detail=)``, ``enforce_rate_limit(error_detail=)``,
   ``send_email(subject=, html=)``, ``render_branded_pdf(title=)``, ``Block(text=, label=)``), or the
   positional detail of ``HTTPException``;
2. a value under a COPY_KEYS key of a dict literal (``{"message": ...}`` in a response body or a stream
   event), or any string inside a ``content=`` dict (a JSONResponse body);
3. assigned to a name or attribute whose last word says which copy it holds (ROLE_NAME:
   ``FEEDBACK_RATE_LIMIT_DETAIL``, ``error_message``, ``run.message``), or returned by a function so
   named (``copilot_taste_exhausted_detail``), unless the name also says the text is for the model
   (``RECOVERY_SYSTEM_MESSAGE``, ``build_system_message``, ``_build_context_message``) or the function
   sits in a prompt module (PROMPT_MODULES: a file named prompt.py or prompts.py), whose returns are
   prompt parts;
4. a module constant that one of the above names (``detail=SOME_CONSTANT``);
5. HTML markup, wherever it sits (a closing tag, or a known element whose attributes carry values):
   mail and PDF bodies;
6. any literal of a DOCUMENT_MODULES file, whose strings are the text of a mail, a PDF, a CSV, a
   workbook or the summary's own fallback markdown;
7. an argument of a call to a dataclass or NamedTuple the module itself defines (with no base it
   inherits fields from), bound by position in field order (a ``field(init=False)``, which ``__init__``
   takes no argument for, holds no position, nor does a ``field(kw_only=True)``, which it takes by name
   only) or by name to a field that is a COPY_FIELDS word or names copy:
   ``ADSRatio(8, "2026-06-28", source, "BABA")``, whose ``source`` PerAdsNote shows as the per-ADS figure's
   tooltip;
8. a list under a TABLE_KEYS key of a dict literal (``{"headers": [...]}``): a table's column headings,
   such as the issuer cash-flow table's.

Never read as copy: docstrings, the arguments of logging calls and ``print``, and the pattern handed to an ``re``
call (its first argument, or ``pattern=``); what else the call takes, a replacement among them, is read as any
literal is.

Checks on that copy: an em-dash (the bare null token ``"—"`` excepted); an exclamation mark (``!=``,
``!important`` and a comment's markup excepted: ``<!--``, ``<![endif]`` and a conditional comment's
condition after its opener, ``<!--[if !mso]>`` or ``<![if !mso]>``; what a comment holds is read as copy);
an emoji or dingbat; an <h1>/<h2> in Title Case. The retired colours (RETIRED_HEX) are checked in every
literal of the scanned files except what is never read (above), since a hex string is only ever a colour.

The account verb (docs/brand/decisions-log.md D-046, F44) is checked in every literal too: the product says
"Log in", "Log out" and "logged in", with "login" the noun, so no literal says "sign in" or "sign out". The verb's
noun is hyphenated and lowercase, like a code token, so the check reads past the eight shapes, and a sentence
handed on through a local without a role word (``note = "Please sign in"`` then ``detail=note``) is read with
the rest; only a module whose file name says its text is for the model (PROMPT_MODULES, MODEL_FACING_NAME) is
read for its copy alone. The other verb is "sign" in any inflection (signs, signed, signing) before "in", "ins",
"into", "out" or "outs", in any case, closed up ("signin"), hyphenated ("sign-in") or parted: by whitespace of any
kind (a line break and a no-break space included), a dash of any kind or the minus sign, and by the words
English puts inside the verb (INSIDE_THE_VERB: "back", "right" or "straight", and an object pronoun, a reflexive
one or one for a person, which may take "all", "both" or "each": "Signing you back in", "Sign them all out"). The
noun as the verb is "login" or "logout" (LOGIN_AS_VERB, a break of its own: ``account verb 'login' as a verb``),
with an "s" or a "re" or neither ("logins", "re-login"), in any case, closed up or hyphenated (a dash of any kind or
the minus sign), in a closed set of places, as INSIDE_THE_VERB is a closed set of words: after "to", "please", a
modal or "do" ("can", "could", "may", "might", "must", "shall", "should", "will", "would", "do", "does" or "did"),
with "not" or contracted ("cannot", "won't", "didn't", "we'll", a straight or a curly apostrophe), or a subject
pronoun ("I", "you", "we", "they", "he", "she" or "it"); before "again", "now", "first" or "here"; and first in a
literal, a line or a sentence, before "with", "to", "into", "using" or "via" (an imperative: "Login with Google"). A
literal is read as its reader gets it: markup (MARKUP) by its text, each tag taken out (TAG; a comment goes with
them, but what a conditional comment holds stays, since Outlook shows it), a block or line-break tag read as a
break (``Sign<br>in``) and an inline one (INLINE) as nothing (``<strong>Sign</strong> in``), and by each
attribute that is not code (CODE_ATTRS: an href, a src, a class, an id, a style), read alone (an
``alt="Sign in"``); a character reference decoded as HTML decodes it (``Sign&nbsp;in``), a compatibility form
folded to its letter (NFKC: a fullwidth ``Ｓｉｇｎ ｉｎ``) and an invisible character taken out (Unicode's
Default_Ignorable_Code_Point: a soft hyphen, a zero-width space or joiner, a word joiner). Each place a literal
says it is a break of its own, on the line of the literal it starts on. "Sign up" (registering), "log in",
"logged in" and "logging in" pass, and so does "login" as the noun, anywhere but in the verb's places ("Too many
login attempts", "Login failed.", "the login page", "A logout ends the session"). Out of reach, each planted as a
gap in VERB_FORMS: the two words in two literals joined by ``+`` (``"Sign " + "in"``), or parted by an
interpolation or a format field (``f"Sign{SPACE}in"``, ``"Sign {}".format("in")``), each part read alone; a tag in
a literal that holds no markup MARKUP knows, read as written (``Sign<wbr>in`` alone); a noun object between them
(``Sign other devices out``; "Sign your name in the box" is the other verb, signing); a letter from another script
(a Cyrillic ``і``); and the noun as the verb anywhere else: in one literal and the word before it in another
(``"Please " + "login"``), alone as a button's label, which reads as the noun (``Login`` alone), after a noun
subject or an adverb (``users who login daily``, ``You can now login``), joined to another verb
(``Register and login with Google``), and an imperative after a colon or after an element whose text ends with
no full stop (``Step 2: login to your account``, ``<h1>Welcome</h1><p>Login to continue</p>``). Its false positives,
planted too: the other senses of "sign" before these words (``Signed into law``, ``A sign right in front of you``),
an attribute that holds code but that CODE_ATTRS does not name (``cite="/signin"``), a code token in kebab case
(``sign-in-limiter``), and the noun in one of the verb's places: after "to" as a preposition (``Back to login``),
after a pronoun that is an object, not the subject (``We'll send you login details``), after a modal that opens a
question or after "May", the month (``Will logout end every session?``, ``In May login attempts rose``), before
one of the four words (``Your login now uses a passkey``), and as the subject or a name that opens a sentence or a
line (``Login with Google is not available.``).

EXEMPT lists what breaks today, each entry with the number of breaks it covers and the PR or decision
that owns their fix: a file, or ``file::function`` for half of one. The number is an equality, as
brandVoiceRules.spec.ts holds its VOICE_RESIDUE, so a new break inside an exempt file or function fails as
it would anywhere else, and a fix that clears some of an entry's breaks lowers its number in the same diff
(a break swapped for another inside one entry in one commit keeps the number: review holds that). It only
shrinks: an entry that no longer covers a break fails as stale, and EXEMPT_CAP equals the count of entries
(an equality, never a ceiling: D-040), so an addition fails and so does a deletion that leaves the cap
where it was. Delete an entry when its owner lands and lower EXEMPT_CAP in the same diff; never raise
either for new copy (a walk that learns a new shape lists what the shape finds and moves the cap in that
commit). Keep the blank line between owner groups so two PRs shrinking different groups merge cleanly.

Limits (review, not this walk): files outside SCAN_DIRS and SCAN_FILES, such as the messages ``app/schemas``'
validators raise, which FastAPI's 422 hands back in its detail (``Message must be at least 10 characters long``);
copy assembled outside these eight shapes in a module that is not a document module, such as a positional
argument of a class defined elsewhere, a list element outside a headers list (a table's rows) or a local
without a role word handed on by name (``x = "..."`` then ``detail=x``); casing below <h2>; and claims, which
brandCopyRules.spec.ts reads. The record shape gives
no position to a ``field(init=False)``, since ``__init__`` takes no argument for it. A ``field(kw_only=True)``
holds no position either, since ``__init__`` takes it by name only, and a keyword argument still binds it. A
class-level ``@dataclass(kw_only=True)`` is not read, so under it a ``field(kw_only=False)`` keeps its declared
place among the keyword-only fields and a positional argument can bind the wrong field; the same holds for a
``field(kw_only=False)`` after a ``_: KW_ONLY`` sentinel, which the walk drops without moving the fields after it
(no scanned module uses either form). It reads no record whose class name or module file name says the text is for the model (MODEL_FACING_NAME), such
as ``recovery_context.py``'s ``RecoveryBlock``, whose labels go into the prompt.
"""
import ast
import html
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("app/routers", "app/services")
SCAN_FILES = ("app/dependencies.py", "main.py")

DOCUMENT_MODULES = frozenset({
    "app/services/ai/markdown_render.py",
    "app/services/analysis_export_metadata.py",
    "app/services/email_service.py",
    "app/services/excel_export_service.py",
    "app/services/export_service.py",
    "app/services/pdf_branding.py",
})

COPY_KEYWORDS = frozenset({
    "detail", "error_detail", "message", "subject", "html", "text", "title", "headline", "label", "speaker",
})
COPY_KEYS = frozenset({"detail", "message", "error", "title", "headline", "label", "subject"})
# A record field that carries copy: the copy keywords, and ``source``, the provenance line a record hands
# the reader beside the figure it qualifies (ADSRatio.source, PerAdsNote's tooltip).
COPY_FIELDS = COPY_KEYWORDS | {"source"}
# A dict key whose list value is a table's column headings.
TABLE_KEYS = frozenset({"headers"})
ROLE_NAME = re.compile(
    r"(?:^|_)(?:detail|message|msg|error|hint|footer|title|headline|subject|html|caption|disclaimer|notice|excerpt)$",
    re.IGNORECASE,
)
# A role name that also says the text is for the model is a prompt part, not copy (RECOVERY_SYSTEM_MESSAGE,
# copilot/prompt.py's _build_context_message); so is a record whose class name or module file name says so
# (recovery_context.py's RecoveryBlock labels).
MODEL_FACING_NAME = re.compile(r"system|prompt|schema|instruction|context", re.IGNORECASE)
# A function in a module with one of these file names builds what the model reads: its returns are not copy.
PROMPT_MODULES = frozenset({"prompt.py", "prompts.py"})
LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})

EM_DASH = "\u2014"
# A conditional comment's condition is markup only after the comment's own opener (<!--[if !mso]>, <![if !mso]>).
NOT_A_BANG = re.compile(r"!=|<!--\[if\s[^\]]*\]|<!\[if\s[^\]]*\]|<!--|<!\[(?:endif|CDATA)|<!doctype|!important", re.IGNORECASE)
EMOJI = re.compile("[\u2600-\u27bf\u2b00-\u2bff\ufe0f\U0001f000-\U0001faff]")  # pictographs, dingbats, symbols, variation selector
RETIRED_HEX = re.compile(r"#(?:10b981|6b7280|e5e1d8|f9f9f9|333|666|ddd)(?![0-9a-f])", re.IGNORECASE)
_ELEMENT = (
    r"(?:a|b|blockquote|body|br|cite|div|em|h[1-6]|head|hr|html|i|img|li|ol|p|pre|section|small|span|strong"
    r"|style|table|td|th|tr|ul)"
)
# A closing tag, or an opening tag whose attributes all carry values: a prompt placeholder such as
# "<a short quote from the filing>" is not markup.
MARKUP = re.compile(
    rf"</{_ELEMENT}\s*>|<{_ELEMENT}(?:\s+[\w:-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'>]+))*\s*/?>",
    re.IGNORECASE,
)
HEADING = re.compile(r"<(h[12])\b[^>]*>(.*?)</\1\s*>", re.IGNORECASE | re.DOTALL)
ANY_TAG = re.compile(r"<[^>]+>")
# Proper names keep their capitals inside a sentence-case heading.
PROPER_NAMES = ("EarningsNerd", "Multi-Period Analysis", "Ask this Filing", "Change Report", "SEC EDGAR", "Pro")

# The account verb (module docstring). What parts its two words once a literal is readable: whitespace of any kind
# (Python's \s takes Unicode's, a no-break space among them), a dash of any kind (Unicode's Pd, as this Python's
# tables list them) and the minus sign.
_DASHES = "".join(chr(code) for code in range(sys.maxunicode + 1) if unicodedata.category(chr(code)) == "Pd")
_PARTED = rf"[\s{re.escape(_DASHES)}\u2212]"
# The words English puts inside the phrasal verb, between "sign" and its particle: "back" and the "right" and
# "straight" that lean on it, and an object pronoun, a reflexive one or one for a person, which may take a floating
# "all", "both" or "each". A closed set, so a noun object stays out (a gap: "Sign other devices out"), as it must:
# "Sign your name in the box" is the other verb, signing.
INSIDE_THE_VERB = (
    r"(?:back|right|straight|(?:me|you|him|her|it|us|them|myself|yourself|himself|herself|itself|ourselves"
    rf"|yourselves|themselves|oneself|everyone|everybody|someone|somebody|anyone|anybody|nobody|no{_PARTED}+one)"
    rf"(?:{_PARTED}+(?:all|both|each))?)"
)
SIGN_IN_VERB = re.compile(
    rf"\bsign(?:s|ed|ing)?(?:{_PARTED}+{INSIDE_THE_VERB})*{_PARTED}*(?:in(?:s|to)?|outs?)\b", re.IGNORECASE
)
# The noun where English puts the verb (module docstring): "login" or "logout", with an "s" or a "re" or neither, closed
# up or hyphenated. Its places are a closed set, as INSIDE_THE_VERB is a closed set of words: after a word that takes
# the bare verb ("to", "please", a modal or "do", with "not" or contracted, a subject pronoun), which the match takes
# with it; before "again", "now", "first" or "here"; and first in a literal, a line or a sentence, before "with", "to",
# "into", "using" or "via" (an imperative). The noun is the group named word: the break names it, on its own line.
_NOUN = rf"(?:re[{re.escape(_DASHES)}\u2212]?)?log[{re.escape(_DASHES)}\u2212]?(?:in|out)s?"
LOGIN_AS_VERB = re.compile(
    r"(?:\b(?:to|please|(?:can|could|may|might|must|shall|should|will|would|do|does|did)(?:\s+not)?|cannot"
    r"|(?:ca|could|might|must|sha|should|wo|would|do|does|did)n['\u2019]t|['\u2019](?:ll|d)|i|you|we|they|he|she|it)\s+"
    rf"|(?:^|(?<=[.!?])\s)\s*(?={_NOUN}\s+(?:with|to|into|using|via)\b)"
    rf"|\b(?={_NOUN}\s+(?:again|now|first|here)\b))(?P<word>{_NOUN})\b",
    re.IGNORECASE | re.MULTILINE,
)
# Unicode's Default_Ignorable_Code_Point (DerivedCoreProperties.txt), which Python's tables do not carry: what a
# reader never sees, such as a soft hyphen, a zero-width space or joiner, a word joiner or a direction mark.
INVISIBLE = re.compile(
    "[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f\u3164"
    "\ufe00-\ufe0f\ufeff\uffa0\ufff0-\ufff8\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e0fff]"
)
# A tag where HTML's tokenizer opens one: "<" and a letter (a start or end tag: its name, then its attributes, which
# may quote a ">"), or "<!" (a comment, either half of a conditional comment, a declaration) or "<?". In markup the
# verb is read by the text between tags and by each attribute that is not code (module docstring).
TAG = re.compile(r"<(?:/?([a-z][^\s/>]*)((?:\"[^\"]*\"|'[^']*'|[^\"'>])*)|[!?][^>]*)>", re.IGNORECASE)
ATTRIBUTE = re.compile(r"""([^\s"'<>/=]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""")
# Elements whose tags put nothing between the words beside them; a comment or a declaration puts nothing either, and
# every other tag reads as a break (a line break, a block, a table cell, an image).
INLINE = frozenset({
    "a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "del", "dfn", "em", "font", "i", "ins", "kbd", "mark",
    "s", "samp", "small", "span", "strong", "sub", "sup", "time", "u", "var", "wbr",
})
# Attributes that hold code, not words: a URL, a name or an id, a class, a style, and the layout and metadata values
# of mail markup. Every other attribute is read as copy (an alt, a title, an aria-label, a placeholder).
CODE_ATTRS = re.compile(
    r"(?:href|src|srcset|action|class|id|name|for|style|role|rel|target|type|lang|dir|charset|http-equiv"
    r"|xmlns(?::[\w-]+)?|width|height|align|valign|border|cellpadding|cellspacing|bgcolor|background|colspan"
    r"|rowspan|data-[\w-]+)",
    re.IGNORECASE,
)

# What breaks today, grouped by the PR or decision that owns the fix: (breaks covered, owner). Both only shrink
# (module docstring).
EXEMPT: dict[str, tuple[int, str]] = {
    "app/services/ai/markdown_render.py": (3, "founder: eval-pinned summary fallback text"),

    "app/routers/contact.py::send_contact_notifications": (11, "backend-mail-templates"),
    "app/routers/feedback.py::_notify_admin": (5, "backend-mail-templates"),
    "app/services/email_service.py": (
        19,
        "backend-mail-templates: the retired colour #6B7280, the em-dashes and the data-quality report's tick "
        "(E46 took the OAuth-linked mail's account verb and its em-dash)",
    ),

    "app/services/ai/issuer_cash_disclosure.py": (1, "backend-copy-high: the issuer cash-flow table's column heading"),
    "app/services/fallback_summary.py": (1, "backend-copy-high"),
    "app/services/summary_sections.py": (1, "backend-copy-high"),

    "app/routers/auth.py::unlink_connection": (
        1,
        "founder: the unlink detail's 'only sign-in method', which test_auth_flow.py pins (a locked contract "
        "test, CLAUDE.md rule 6), so it takes the account verb only under a contract change its PR documents; F56",
    ),
    "app/services/trend_analysis/detectors.py": (
        1,
        "founder: the cash-conversion red flag's sentence is in the observation selector's prompt bytes and the "
        "dataset fingerprint (test_trend_refactor_anchors.py T0.2, T0.3), so its em-dash goes with a PROMPT_VERSION "
        "bump and the spot-check backend/evals/RUNBOOK.md asks of one (Multi-Period Analysis observation-selector gate); E138",
    ),
}
# The entry count, held as an equality (D-040): 18 when the gate landed, 20 when the walk learned shapes 7
# and 8 and listed the two files they found in the same commit, 16 when the backend-exports PR (#1345) landed
# and its four entries went, 13 when the five routers' voice pass (E45) took four of its five entries off (the
# red flag's waits for a PROMPT_VERSION event, see its entry) and the account verb, learned in the same commit,
# listed the one break a locked test pins, 9 when the summary pipeline's stream sentences took the voice with
# E217's functional change to summary_stages (F35, D-046; E92) and their four entries went. Lower it with every
# deletion, in the same diff; when two shrinking PRs meet, the later merge sets it to the merged list's count, which
# the equality holds it to. Raising it for new copy is the one change this gate exists to refuse.
EXEMPT_CAP = 9


@dataclass(frozen=True)
class Break:
    path: str
    line: int
    scope: str
    rule: str
    text: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" + (f" ({self.scope})" if self.scope else "")
        return f"{where} {self.rule}: {self.text[:100]!r}"


def _text(node: ast.AST) -> str:
    """A literal's text; an f-string's interpolations read as ``{}``."""
    if isinstance(node, ast.Constant):
        return node.value
    return "".join(part.value if isinstance(part, ast.Constant) else "{}" for part in node.values)


def _copy_breaks(text: str) -> Iterator[tuple[int, str]]:
    """(offset, rule) for each voice break in a piece of copy."""
    if EM_DASH in text and text.strip() != EM_DASH:
        yield text.index(EM_DASH), "em-dash"
    allowed = {i for match in NOT_A_BANG.finditer(text) for i in range(match.start(), match.end())}
    bangs = [i for i, char in enumerate(text) if char == "!" and i not in allowed]
    if bangs:
        yield bangs[0], "exclamation mark"
    emoji = EMOJI.search(text)
    if emoji:
        yield emoji.start(), "emoji"
    for heading in HEADING.finditer(text):
        words = html.unescape(ANY_TAG.sub(" ", heading.group(2))).replace("{}", " ")
        for name in PROPER_NAMES:
            words = words.replace(name, " ")
        tail = [word.strip(".,:;()&'\"") for word in words.split()][1:]
        if any(word[:1].isupper() and not word.isupper() for word in tail):
            yield heading.start(), f"Title Case <{heading.group(1)}>"


def _account_verb(text: str) -> Iterator[tuple[int, str]]:
    """(line breaks in ``text`` before it, rule) for each place a literal says the other verb, or the noun where English
    puts the verb (at the noun's own place), read as its reader gets it (module docstring)."""
    for reading, stretches in _readings(text):
        found = [(match.start(), f"account verb {match.group(0)!r}") for match in SIGN_IN_VERB.finditer(reading)]
        found += [
            (match.start("word"), f"account verb {match.group('word')!r} as a verb")
            for match in LOGIN_AS_VERB.finditer(reading)
        ]
        for at, rule in found:
            start, lines = max(stretch for stretch in stretches if stretch[0] <= at)
            yield lines + reading.count("\n", start, at), rule


def _readings(text: str) -> Iterator[tuple[str, list[tuple[int, int]]]]:
    """A literal's text as its reader gets it (module docstring), each reading with where its stretches start: (offset
    in the reading, line breaks in ``text`` before the stretch). Markup (MARKUP) is read by its text, each tag taken
    out (INLINE as nothing, any other as a break), and by each attribute that is not code (CODE_ATTRS), read alone;
    any other literal as written."""
    if not MARKUP.search(text):
        yield _fold(text), [(0, 0)]
        return
    reading, stretches, at = "", [], 0
    for tag in TAG.finditer(text):
        stretches.append((len(reading), text.count("\n", 0, at)))
        name = (tag.group(1) or "").lower()
        reading += _fold(text[at:tag.start()]) + ("" if not name or name in INLINE else " ")
        for attribute in ATTRIBUTE.finditer(tag.group(2) or ""):
            if not CODE_ATTRS.fullmatch(attribute.group(1)):
                value = next(group for group in (2, 3, 4) if attribute.group(group) is not None)
                where = tag.start(2) + attribute.start(value)
                yield _fold(attribute.group(value)), [(0, text.count("\n", 0, where))]
        at = tag.end()
    stretches.append((len(reading), text.count("\n", 0, at)))
    yield reading + _fold(text[at:]), stretches


def _fold(text: str) -> str:
    """A run of text with its character references decoded as HTML decodes them, its compatibility forms folded to
    their letters (NFKC) and its invisible characters taken out, line by line, so it keeps the line breaks of the
    source and no others (a decoded ``&#10;`` reads as a space)."""
    return "\n".join(
        INVISIBLE.sub("", unicodedata.normalize("NFKC", html.unescape(line))).replace("\n", " ")
        for line in text.split("\n")
    )


class _Reader(ast.NodeVisitor):
    """Collect the literals of one module, which of them reach a user, and each literal's scope."""

    def __init__(self, tree: ast.Module, prompt_module: bool = False, model_module: bool = False) -> None:
        self.prompt_module = prompt_module
        self.constants: dict[str, ast.expr] = {}
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                self.constants[stmt.targets[0].id] = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
                self.constants[stmt.target.id] = stmt.value
        self.records = self._records(tree, model_module)
        self.skip = self._skipped(tree)
        self.reached: set[int] = set()
        self.literals: list[tuple[ast.AST, str]] = []
        self._scope: list[str] = []
        self._functions: list[str] = []
        self.visit(tree)

    @staticmethod
    def _records(tree: ast.Module, model_module: bool = False) -> dict[str, list[str]]:
        """Field names of each dataclass or NamedTuple the module defines without inheriting fields, in the order
        ``__init__`` takes them: less any ``field(init=False)``, which takes no argument, and with each
        ``field(kw_only=True)`` after the positional fields, where only a keyword reaches it (a class-level
        ``@dataclass(kw_only=True)`` and the ``_: KW_ONLY`` sentinel's reach are not read: Limits); none for a
        class, or in a module, whose name says it is for the model."""
        records: dict[str, list[str]] = {}
        if model_module:
            return records
        for stmt in tree.body:
            if not isinstance(stmt, ast.ClassDef) or MODEL_FACING_NAME.search(stmt.name):
                continue
            bases = [_dotted_tail(base) for base in stmt.bases]
            named_tuple = bases == ["NamedTuple"]
            is_dataclass = not bases and any(
                _dotted_tail(d.func if isinstance(d, ast.Call) else d) == "dataclass" for d in stmt.decorator_list
            )
            if named_tuple or is_dataclass:
                fields = [
                    item for item in stmt.body
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
                    and not re.search(r"\b(?:ClassVar|KW_ONLY)\b", ast.unparse(item.annotation))
                    and not _init_false(item.value)
                ]
                # The stable sort moves each field(kw_only=True) behind the positional fields, as __init__ orders
                # them: no positional argument binds it, and a keyword still does (dropping it would lose that).
                records[stmt.name] = [item.target.id for item in sorted(fields, key=lambda item: _kw_only(item.value))]
        return records

    @staticmethod
    def _skipped(tree: ast.Module) -> set[int]:
        """Docstrings, everything inside a logging or print call, and the pattern an ``re`` call takes."""
        skip: set[int] = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body:
                first = body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                    skip.add(id(first.value))
            if isinstance(node, ast.Call) and _is_log_call(node):
                skip.update(id(sub) for sub in ast.walk(node))
            elif isinstance(node, ast.Call) and (pattern := _re_pattern(node)) is not None:
                skip.update(id(sub) for sub in ast.walk(pattern))
        return skip

    def _where(self) -> str:
        return ".".join(self._scope)

    def _reach(self, expr: Optional[ast.AST], seen: frozenset[str] = frozenset()) -> None:
        if expr is None:
            return
        if isinstance(expr, (ast.Constant, ast.JoinedStr)):
            if isinstance(expr, ast.JoinedStr) or isinstance(expr.value, str):
                self.reached.add(id(expr))
            if isinstance(expr, ast.JoinedStr):
                for part in expr.values:
                    if isinstance(part, ast.FormattedValue):
                        self._reach(part.value, seen)
        elif isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Mod)):
            self._reach(expr.left, seen)
            self._reach(expr.right, seen)
        elif isinstance(expr, ast.IfExp):
            self._reach(expr.body, seen)
            self._reach(expr.orelse, seen)
        elif isinstance(expr, ast.BoolOp):
            for value in expr.values:
                self._reach(value, seen)
        elif isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
            for element in expr.elts:
                self._reach(element, seen)
        elif isinstance(expr, ast.Dict):
            for value in expr.values:
                self._reach(value, seen)
        elif isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr in {"format", "join"}:
            self._reach(expr.func.value, seen)
            for arg in expr.args:
                self._reach(arg, seen)
        elif isinstance(expr, ast.Name) and expr.id in self.constants and expr.id not in seen:
            self._reach(self.constants[expr.id], seen | {expr.id})

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._functions.append(node.name)  # the innermost one decides what a ``return`` hands back
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()
        self._functions.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Return(self, node: ast.Return) -> None:
        if self._functions and not self.prompt_module and _names_copy(self._functions[-1]):
            self._reach(node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        for keyword in node.keywords:
            if keyword.arg in COPY_KEYWORDS or keyword.arg == "content":
                self._reach(keyword.value)
        if _call_name(node) == "HTTPException" and len(node.args) >= 2:
            self._reach(node.args[1])
        fields = self.records.get(node.func.id) if isinstance(node.func, ast.Name) else None
        if fields is not None:
            bound = list(zip(fields, node.args)) + [(k.arg, k.value) for k in node.keywords if k.arg in fields]
            for field, value in bound:
                if field in COPY_FIELDS or _names_copy(field):
                    self._reach(value)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value in COPY_KEYS:
                self._reach(value)
            elif isinstance(key, ast.Constant) and key.value in TABLE_KEYS and isinstance(value, (ast.List, ast.Tuple)):
                self._reach(value)
        self.generic_visit(node)

    def _assigned(self, targets: list[ast.expr], value: Optional[ast.AST]) -> None:
        for target in targets:
            name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ""
            if name and _names_copy(name):
                self._reach(value)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._assigned(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._assigned([node.target], node.value)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._assigned([node.target], node.value)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and id(node) not in self.skip:
            self.literals.append((node, self._where()))

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        if id(node) not in self.skip:
            self.literals.append((node, self._where()))
        for part in node.values:  # the constant parts belong to this literal; read only the interpolations
            if isinstance(part, ast.FormattedValue):
                self.visit(part.value)


def _names_copy(name: str) -> bool:
    """A name whose last word says which copy it holds, and that does not say the text is for the model."""
    return bool(ROLE_NAME.search(name)) and not MODEL_FACING_NAME.search(name)


def _dotted_tail(node: ast.expr) -> str:
    """``dataclass`` for ``dataclass`` and ``dataclasses.dataclass``."""
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""


def _init_false(value: Optional[ast.expr]) -> bool:
    """``field(init=False)``: a dataclass field that ``__init__`` takes no argument for."""
    return isinstance(value, ast.Call) and _dotted_tail(value.func) == "field" and any(
        k.arg == "init" and isinstance(k.value, ast.Constant) and k.value.value is False for k in value.keywords
    )


def _kw_only(value: Optional[ast.expr]) -> bool:
    """``field(kw_only=True)``: a dataclass field that ``__init__`` takes by keyword only, after every positional one."""
    return isinstance(value, ast.Call) and _dotted_tail(value.func) == "field" and any(
        k.arg == "kw_only" and isinstance(k.value, ast.Constant) and k.value.value is True for k in value.keywords
    )


def _call_name(node: ast.Call) -> str:
    func = node.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""


def _owner(func: ast.Attribute) -> str:
    """``re`` for ``re.sub``, ``logger`` for ``self.logger.info``."""
    return _dotted_tail(func.value)


def _is_log_call(node: ast.Call) -> bool:
    """``print``, or a LOG_METHODS method of an owner whose name says it logs."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    return isinstance(func, ast.Attribute) and func.attr in LOG_METHODS and "log" in _owner(func).lower()


def _re_pattern(node: ast.Call) -> Optional[ast.expr]:
    """The pattern an ``re`` call takes (its first argument, or ``pattern=``); None for any other call."""
    if not (isinstance(node.func, ast.Attribute) and _owner(node.func) == "re"):
        return None
    return node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "pattern"), None)


def read_module(source: str, path: str) -> tuple[list[Break], int]:
    """(breaks, copy literals read) for one module; ``path`` (relative to backend/) sets the document mode, and
    its file name the prompt-module and model-record modes."""
    module = Path(path)
    reader = _Reader(
        ast.parse(source),
        prompt_module=module.name in PROMPT_MODULES,
        model_module=bool(MODEL_FACING_NAME.search(module.stem)),
    )
    # A module whose file name says its text is for the model is read for the account verb in its copy alone.
    model_text = module.name in PROMPT_MODULES or bool(MODEL_FACING_NAME.search(module.stem))
    found: list[Break] = []
    verbs: list[Break] = []  # each place a literal says the other verb is a break of its own, never merged
    copy = 0
    for node, scope in reader.literals:
        text = _text(node)
        is_copy = path in DOCUMENT_MODULES or id(node) in reader.reached or bool(MARKUP.search(text))
        if is_copy:
            copy += 1
            for offset, rule in _copy_breaks(text):
                found.append(Break(path, node.lineno + text.count("\n", 0, offset), scope, rule, text.strip()))
        for colour in RETIRED_HEX.finditer(text):
            line = node.lineno + text.count("\n", 0, colour.start())
            found.append(Break(path, line, scope, f"retired colour {colour.group(0)}", text.strip()))
        if is_copy or not model_text:
            for lines, rule in _account_verb(text):
                verbs.append(Break(path, node.lineno + lines, scope, rule, text.strip()))
    return sorted([*set(found), *verbs], key=lambda b: (b.path, b.line, b.rule)), copy


def breaks_in(source: str, path: str) -> list[Break]:
    return read_module(source, path)[0]


def scanned_files() -> list[str]:
    files = [path for d in SCAN_DIRS for path in sorted((BACKEND_DIR / d).rglob("*.py"))]
    files += [BACKEND_DIR / f for f in SCAN_FILES]
    return [str(path.relative_to(BACKEND_DIR)) for path in files]


def all_breaks() -> list[Break]:
    return [b for rel in scanned_files() for b in breaks_in((BACKEND_DIR / rel).read_text(encoding="utf-8"), rel)]


def _breaks_by_entry() -> tuple[list[Break], dict[str, list[Break]]]:
    """(breaks no entry covers, breaks per EXEMPT entry)."""
    loose: list[Break] = []
    covered: dict[str, list[Break]] = {entry: [] for entry in EXEMPT}
    for item in all_breaks():
        entry = exempt_entry(item)
        if entry is None:
            loose.append(item)
        else:
            covered[entry].append(item)
    return loose, covered


def exempt_entry(item: Break) -> Optional[str]:
    """The EXEMPT entry covering a break: its file, or its file and enclosing function."""
    for entry in EXEMPT:
        path, _, scope = entry.partition("::")
        if path == item.path and (not scope or item.scope == scope or item.scope.startswith(scope + ".")):
            return entry
    return None


# A gate that cannot fail proves nothing: every shape it reads, and every shape it must let through.
_PROBE = '''
"""A module docstring may say anything — even "Done!"."""
import logging
import re

logger = logging.getLogger(__name__)
SLOW_DOWN = "Slow down!"
RATE_LIMIT_DETAIL = "Too many requests — wait a minute."
RECOVERY_SYSTEM_MESSAGE = "Fill the gaps — return JSON."
PALETTE = {"ink": "#333", "brand": "#3333FF"}
SEPARATOR = re.compile(r"[—–-]")


def route(n, run):
    """A docstring is not copy — not even "this!"."""
    logger.info("joined — %s!", n)
    token = "a — b"
    snippet = "<a short quote — never reword>"
    error_message = f"{n} items — retry"
    enforce_rate_limit(error_detail=SLOW_DOWN)
    if n:
        raise HTTPException(404, "Gone!")
    if n > 2:
        raise HTTPException(400, "Try again [if you can!]")
    if n > 1:
        raise HTTPException(status_code=409, detail="This report is out of date — run it again.")
    run.message = "Hold on — joining."
    page = '<p style="color:#6B7280">Hi there</p><h2>Thank You for Writing</h2><h2>Welcome to EarningsNerd</h2>'
    fine = '<!-- note --><style>p {color: red !important}</style><p>a != b</p><!--[if !mso]><!-->x<!--<![endif]--><![if !mso]>y<![endif]>'
    bracket = "Your link expires soon [if unused, request another one!]"
    held = '<!--[if mso]><p>Welcome aboard!</p><![endif]-->'
    revealed = '<![if !mso]><p>Welcome back!</p><![endif]>'
    shown = '<!--[if !mso]><!--><p>Welcome aboard!</p><!--<![endif]-->'
    return JSONResponse(content={"success": False, "reason": "Oops — no", "message": "Saved ✨", "empty": "—"})


def taste_detail(n):
    def fallback():
        return "Inner — not a detail"
    return f"You have used {n} questions!"


def build_system_message(n):
    return "Plan — answer as JSON!"


def _build_context_message(n):
    return "FILING: Apple — 10-K filed today!"


@dataclass(frozen=True)
class Ratio:
    per_ads: float
    source: str
    ticker: str
    KIND: ClassVar[str] = "ClassVar — not a field"


class Row(NamedTuple):
    label: str
    note: str


@dataclass
class Derived(Ratio):
    caption: str


@dataclass
class Note:
    stamp: float = field(init=False)
    figure: int = 0
    source: str = ""


@dataclass
class KwNote:
    stamp: float = field(kw_only=True, default=0)
    figure: int = 0
    source: str = ""
    caption: str = field(kw_only=True, default="")


RATIOS = {
    "a": Ratio(8, "Deposit agreement — 1 ADS = 8 shares", "B — A"),
    "b": Ratio(per_ads=5, ticker="T — M", source="Cover page — 1 ADS = 5 shares"),
}
ROWS = [Row("Free cash — flow", "plain — note"), Elsewhere(1, "Defined elsewhere — not read")]
DERIVED = Derived("Inherited fields — not mapped", "X", "Y", "Z")  # caption, its own field, follows the 3 it inherits
NOTES = [Note(3, "Cover — 1 ADS = 3 shares")]  # stamp takes no argument: 3 is the figure, the string the source
# stamp takes a keyword only, so 3 is the figure and the string the source; caption, keyword-only too, binds by name
KW_NOTES = [KwNote(3, "Cover — 1 ADS"), KwNote(caption="Caption — by name only")]
TABLE = {
    "headers": ["USD millions — year ended", *YEARS],
    "rows": [["Cash — net", 1]],
    "request": {"headers": {"X-Note": "a header — not copy"}},
}
'''

# A prompt module's role-named returns are prompt parts; the same function elsewhere returns copy.
_PROMPT_PROBE = '''
def refusal_message(n):
    return f"No answer — {n} sources!"
'''

# A record whose class name, or whose module's file name, says it is for the model is a prompt part; the same
# plain record in any other module is read (recovery_context.py's RecoveryBlock labels go into the prompt).
_MODEL_RECORD_PROBE = '''
@dataclass
class Block:
    kind: str
    text: str


@dataclass
class PromptPart:
    kind: str
    text: str


def recovery():
    return Block("FILING", "Filing excerpt — model reads this")


def rules():
    return PromptPart("RULES", "Quote the filing — never reword")
'''

_PAGE = '<p style="color:#6B7280">Hi there</p><h2>Thank You for Writing</h2><h2>Welcome to EarningsNerd</h2>'
_PROBE_BREAKS = {
    ("exclamation mark", "Slow down!"),
    ("em-dash", "Too many requests — wait a minute."),
    ("retired colour #333", "#333"),
    ("em-dash", "{} items — retry"),
    ("exclamation mark", "Gone!"),
    ("exclamation mark", "Try again [if you can!]"),
    ("exclamation mark", "<!--[if mso]><p>Welcome aboard!</p><![endif]-->"),
    ("exclamation mark", "<![if !mso]><p>Welcome back!</p><![endif]>"),
    ("exclamation mark", "<!--[if !mso]><!--><p>Welcome aboard!</p><!--<![endif]-->"),
    ("em-dash", "This report is out of date — run it again."),
    ("em-dash", "Hold on — joining."),
    ("retired colour #6B7280", _PAGE),
    ("Title Case <h2>", _PAGE),
    ("em-dash", "Oops — no"),
    ("emoji", "Saved ✨"),
    ("exclamation mark", "You have used {} questions!"),
    ("em-dash", "Deposit agreement — 1 ADS = 8 shares"),
    ("em-dash", "Cover page — 1 ADS = 5 shares"),
    ("em-dash", "Free cash — flow"),
    ("em-dash", "Cover — 1 ADS = 3 shares"),
    ("em-dash", "Cover — 1 ADS"),
    ("em-dash", "Caption — by name only"),
    ("em-dash", "USD millions — year ended"),
}


def test_the_reader_sees_each_shape_and_lets_the_rest_through():
    found = breaks_in(_PROBE, "app/routers/probe.py")
    assert {(b.rule, b.text) for b in found} == _PROBE_BREAKS
    assert [b.line for b in found if b.text == "Slow down!"] == [7]  # the constant's own line, not its use
    assert {b.scope for b in found if b.text == "Gone!"} == {"route"}
    assert {b.scope for b in found if b.text.startswith("You have used")} == {"taste_detail"}

    # In a document module every literal is text, so the plain ones count too; docstrings, logging and
    # patterns still do not.
    document = {(b.rule, b.text) for b in breaks_in(_PROBE, "app/services/email_service.py")}
    assert document - _PROBE_BREAKS == {
        ("em-dash", "a — b"),
        ("em-dash", "<a short quote — never reword>"),
        ("em-dash", "Fill the gaps — return JSON."),
        ("em-dash", "Inner — not a detail"),
        ("em-dash", "Plan — answer as JSON!"),
        ("exclamation mark", "Plan — answer as JSON!"),
        ("em-dash", "FILING: Apple — 10-K filed today!"),
        ("exclamation mark", "FILING: Apple — 10-K filed today!"),
        ("em-dash", "ClassVar — not a field"),
        ("em-dash", "B — A"),
        ("em-dash", "T — M"),
        ("em-dash", "plain — note"),
        ("em-dash", "Defined elsewhere — not read"),
        ("em-dash", "Inherited fields — not mapped"),
        ("em-dash", "Cash — net"),
        ("em-dash", "a header — not copy"),
        ("exclamation mark", "Your link expires soon [if unused, request another one!]"),
    }

    # A role-named return in prompt.py or prompts.py is not read; in any other module it is.
    assert breaks_in(_PROMPT_PROBE, "app/services/copilot/prompt.py") == []
    assert breaks_in(_PROMPT_PROBE, "app/services/ai/prompts.py") == []
    assert {(b.rule, b.scope) for b in breaks_in(_PROMPT_PROBE, "app/services/copilot/answer.py")} == {
        ("em-dash", "refusal_message"), ("exclamation mark", "refusal_message"),
    }

    # No record is read in a module whose file name says it is for the model, nor one whose class name says so
    # anywhere; the plain record in any other module is.
    assert breaks_in(_MODEL_RECORD_PROBE, "app/services/ai/recovery_context.py") == []
    assert {(b.rule, b.text) for b in breaks_in(_MODEL_RECORD_PROBE, "app/services/ai/recovery.py")} == {
        ("em-dash", "Filing excerpt — model reads this"),
    }

    # The real Copilot paywall detail is still read: its f-string counts as copy.
    source = (BACKEND_DIR / "app/dependencies.py").read_text(encoding="utf-8")
    reader = _Reader(ast.parse(source))
    taste = [node for node, scope in reader.literals if scope == "copilot_taste_exhausted_detail" and id(node) in reader.reached]
    assert any("free Copilot questions" in _text(node) for node in taste), "copilot_taste_exhausted_detail is no longer read"


# The account verb's planted forms (module docstring; lessons/test-gates-must-be-as-wide-as-their-rule.md), each a
# statement in the body of a probe route and the mark the walk must score it with: "flag", a form of the other verb
# it fails; "clean", a look-alike it lets through; "gap", a form the rule forbids that it passes; "false positive",
# another sense of "sign" or a code token it fails. Each gap and false positive is named in the module docstring
# (the third field, as the docstring writes it, never empty), so the header and the cases move together.
VERB_FORMS: tuple[tuple[str, str, str], ...] = (
    (r'raise HTTPException(401, "Sign in to continue.")', "flag", ""),
    (r'raise HTTPException(status_code=429, detail="Too many sign-in attempts. Please try again shortly.")', "flag", ""),
    (r'raise HTTPException(status_code=503, detail="Google Sign-In is not configured.")', "flag", ""),
    (r'raise HTTPException(status_code=503, detail="Apple Sign In is not configured.")', "flag", ""),
    ('raise HTTPException(400, detail="You can\'t remove your only sign-in method.")', "flag", ""),
    (r'message = f"You are signed in as {name}."', "flag", ""),
    (r'loading = "Signing in…"', "flag", ""),
    (r'label = "Signs out of every device"', "flag", ""),
    (r'label = "SIGN OUT"', "flag", ""),
    (r'label = "Sign into your account"', "flag", ""),
    (r'label = "No social sign-ins linked."', "flag", ""),
    (r'label = "Signin failed"', "flag", ""),
    (r'label = "Signout failed"', "flag", ""),
    (r'label = "Readers who are signed-out see the teaser"', "flag", ""),
    (r'label = "Sign\u00a0in"', "flag", ""),  # a no-break space
    (r'label = "Sign\u2011in"', "flag", ""),  # a non-breaking hyphen
    (r'label = "Sign\u2013in"', "flag", ""),  # an en dash
    (r'label = "Sign\u2212in"', "flag", ""),  # the minus sign
    (r'label = "Already have an account? Sign\n  in"', "flag", ""),  # a line break
    (r'label = "Signing you back in…"', "flag", ""),
    (r'label = "Sign them all out"', "flag", ""),
    (r'html = "<p>Sign&nbsp;in to continue</p>"', "flag", ""),  # a character reference, decoded as HTML decodes it
    (r'html = "<p>Sign&#8209;in</p>"', "flag", ""),
    (r'label = "\uff33\uff49\uff47\uff4e \uff49\uff4e"', "flag", ""),  # fullwidth letters, which NFKC folds
    (r'label = "Sig\u200bn in"', "flag", ""),  # a zero-width space inside the word
    (r'label = "Sign\u00adin"', "flag", ""),  # a soft hyphen
    (r'note = "Please sign in."; raise HTTPException(401, note)', "flag", ""),  # a local with no role word, handed on
    (r'text = "Sign " "in"', "flag", ""),  # adjacent literals, which the parser joins
    (r'html = "<p><strong>Sign</strong> in to continue</p>"', "flag", ""),  # an inline tag reads as nothing
    (r'html = "<p>Sign<wbr>in</p>"', "flag", ""),
    (r'html = "<p>Sign <span>in</span></p>"', "flag", ""),
    ('html = \'<a href="/login">Sign</a> in\'', "flag", ""),
    (r'html = "<p>Sign<br>in</p>"', "flag", ""),  # a line-break tag reads as a break
    (r'html = "<!--[if mso]><p>Sign in</p><![endif]-->"', "flag", ""),  # what a conditional comment holds
    ('html = \'<img src="/logo.png" alt="Sign in to EarningsNerd">\'', "flag", ""),  # an attribute that is not code
    (r'label = re.sub("x", "Sign in again", name)', "flag", ""),  # what an re call takes besides its pattern
    (r'"""Sign in to continue."""', "clean", ""),  # a docstring is never copy
    (r'logger.info("sign in failed for %s", name)', "clean", ""),  # nor a log line
    (r'PATTERN = re.compile("sign in")', "clean", ""),  # nor a pattern
    (r'label = re.sub(pattern="sign in", repl="log in", string=name)', "clean", ""),  # nor one passed by name
    ('html = \'<a href="/signin">Open the page</a>\'', "clean", ""),  # an attribute that holds code
    ('html = \'<p class="signin-note" id="sign-in">Log in to continue.</p>\'', "clean", ""),
    (r'html = "<p>Log in.</p><!-- sign in was the old verb -->"', "clean", ""),  # a comment goes with the tags
    (r'html = "<p>De<span>sign</span> in public</p>"', "clean", ""),  # an inline tag parts no word
    (r'raise HTTPException(401, "Log in to continue.")', "clean", ""),
    (r'label = "You are logged in as {}."', "clean", ""),
    (r'loading = "Logging in…"', "clean", ""),
    (r'label = "Log out of all devices"', "clean", ""),
    (r'label = "Login failed"', "clean", ""),
    (r'label = "Sign up for alerts"', "clean", ""),
    (r'label = "Already signed up? Log in."', "clean", ""),
    (r'label = "sign-up or signup"', "clean", ""),
    (r'raise HTTPException(400, detail="Missing stripe-signature header")', "clean", ""),
    (r'label = "The webhook signing secret is not set."', "clean", ""),
    (r'label = "Signals in the filing"', "clean", ""),
    (r'label = "Assign it in settings, or resign in protest."', "clean", ""),
    (r'label = "Designing in public"', "clean", ""),
    (r'key = "sign_in_url"', "clean", ""),
    (r'label = "Sign your name in the box"', "clean", ""),  # the other verb, signing
    (r'label = "Sign " + "in"', "gap", '``"Sign " + "in"``'),
    (r'label = f"Sign{SPACE}in"', "gap", '``f"Sign{SPACE}in"``'),
    (r'label = "Sign {}".format("in")', "gap", '``"Sign {}".format("in")``'),
    (r'label = "Sign<wbr>in"', "gap", "``Sign<wbr>in`` alone"),  # MARKUP knows no wbr, so the literal is not markup
    (r'label = "Sign other devices out"', "gap", "``Sign other devices out``"),
    (r'label = "Sign \u0456n"', "gap", "a Cyrillic ``\u0456``"),  # NFKC folds no letter of another script
    (r'label = "Signed into law"', "false positive", "``Signed into law``"),
    (r'label = "A sign right in front of you"', "false positive", "``A sign right in front of you``"),
    ('html = \'<blockquote cite="/signin">Quoted</blockquote>\'', "false positive", '``cite="/signin"``'),
    (r'key = "sign-in-limiter"', "false positive", "``sign-in-limiter``"),
    # The noun as the verb (LOGIN_AS_VERB): each of its places, the noun's other spellings and the reading a literal
    # gets; the noun and the two-word verb, clean; and its gaps and false positives.
    (r'raise HTTPException(401, "Please login again.")', "flag", ""),  # the review's two examples
    (r'label = "Logout now."', "flag", ""),
    (r'label = "You need to login to continue."', "flag", ""),
    (r'label = "You must login with your email."', "flag", ""),
    ('label = "You can\'t login while the account is locked."', "flag", ""),
    (r'label = "Readers cannot logout of a shared device."', "flag", ""),
    (r'label = "We won\u2019t logout your other devices."', "flag", ""),  # a curly apostrophe
    ('label = "If you didn\'t login, reset your password."', "flag", ""),
    (r'label = "Do not logout during an export."', "flag", ""),
    ('label = "We\'ll logout every device."', "flag", ""),
    (r'message = f"Once you login, {name} opens."', "flag", ""),
    (r'label = "If she logins from a new device, we send a notice."', "flag", ""),
    (r'label = "Session ended: login again."', "flag", ""),
    (r'label = "Login first, then add a filing."', "flag", ""),
    (r'label = "Login here"', "flag", ""),
    (r'label = "Login with Google"', "flag", ""),
    (r'label = "Login to EarningsNerd"', "flag", ""),
    (r'label = "Login into your account."', "flag", ""),
    (r'label = "Login using your passkey."', "flag", ""),
    (r'label = "Login via the link we sent."', "flag", ""),
    (r'raise HTTPException(401, "Your session ended. Login to continue.")', "flag", ""),  # a sentence's start
    (r'message = f"Hi {name},\n\nLogin to finish setting up your account."', "flag", ""),  # a line's start
    (r'label = "Please log-in again."', "flag", ""),
    (r'label = "Please re-login."', "flag", ""),
    (r'label = "LOGOUT NOW"', "flag", ""),
    (r'html = "<p>Please <strong>login</strong> again.</p>"', "flag", ""),  # an inline tag reads as nothing
    ('html = \'<img src="/g.png" alt="Login with Google">\'', "flag", ""),  # an attribute that is not code
    (r'html = "<p>Please&nbsp;log&#8209;in again.</p>"', "flag", ""),  # character references
    (r'label = "\uff2c\uff4f\uff47\uff49\uff4e to continue"', "flag", ""),  # fullwidth letters, which NFKC folds
    (r'label = "Please lo\u200bgin again."', "flag", ""),  # a zero-width space inside the word
    (r'raise HTTPException(status_code=429, detail="Too many login attempts. Try again shortly.")', "clean", ""),
    (r'label = "Check your login and password."', "clean", ""),
    (r'label = "Open the login page."', "clean", ""),
    (r'label = "Login required"', "clean", ""),
    (r'label = "Logins this week"', "clean", ""),
    (r'label = "A logout ends the session."', "clean", ""),
    (r'raise HTTPException(status_code=503, detail="Logging in with Google is not available.")', "clean", ""),
    (r'label = "Your log-in link expires in an hour."', "clean", ""),  # the hyphenated noun
    (r'raise HTTPException(401, "Please log in again.")', "clean", ""),  # the verb, two words, in the noun's places
    (r'label = "Log out now."', "clean", ""),
    (r'label = "Log in with Google"', "clean", ""),
    ('label = "If you didn\'t log in, reset your password."', "clean", ""),
    (r'url = f"{name}/login?error=google_denied"', "clean", ""),  # a path
    (r'label = "Please " + "login"', "gap", '``"Please " + "login"``'),
    (r'label = "Login"', "gap", "``Login`` alone"),
    (r'label = "Alerts go to users who login daily."', "gap", "``users who login daily``"),
    (r'label = "You can now login"', "gap", "``You can now login``"),
    (r'label = "Register and login with Google"', "gap", "``Register and login with Google``"),
    (r'label = "Step 2: login to your account"', "gap", "``Step 2: login to your account``"),
    (r'html = "<h1>Welcome</h1><p>Login to continue</p>"', "gap", "``<h1>Welcome</h1><p>Login to continue</p>``"),
    (r'label = "Back to login"', "false positive", "``Back to login``"),
    ('label = "We\'ll send you login details."', "false positive", "``We'll send you login details``"),
    (r'label = "Will logout end every session?"', "false positive", "``Will logout end every session?``"),
    (r'label = "In May login attempts rose."', "false positive", "``In May login attempts rose``"),
    (r'label = "Your login now uses a passkey."', "false positive", "``Your login now uses a passkey``"),
    (
        r'raise HTTPException(status_code=503, detail="Login with Google is not available.")',
        "false positive",
        "``Login with Google is not available.``",
    ),
)
# How many cases carry each mark, held equal so that a case dropped in an edit fails here.
VERB_MARKS = {"flag": 66, "clean": 36, "gap": 13, "false positive": 10}


def _verbs(source: str, path: str = "app/routers/probe.py") -> list[Break]:
    return [item for item in breaks_in(source, path) if item.rule.startswith("account verb")]


def test_the_verb_check_scores_its_planted_forms():
    assert Counter(mark for _, mark, _ in VERB_FORMS) == VERB_MARKS
    scored = [
        (statement, mark, _verbs(f"def route(name, x, SPACE):\n    {statement}\n"))
        for statement, mark, _ in VERB_FORMS
    ]
    wrong = [
        f"{mark}: {statement} -> {[str(item) for item in found]}"
        for statement, mark, found in scored
        if bool(found) != (mark in {"flag", "false positive"})
    ]
    assert not wrong, "The account verb check scored a planted form wrongly:\n" + "\n".join(wrong)
    # An empty name would pass ("" is in every string), so a gap or a false positive needs one.
    unnamed = [
        statement for statement, mark, named in VERB_FORMS
        if mark in {"gap", "false positive"} and not (named.strip() and named in __doc__)
    ]
    assert not unnamed, f"The module docstring names no gap or false positive for these planted forms: {unnamed}"

    # Each place a literal says it is a break of its own, on the line it starts on; a module whose file name says
    # its text is for the model is read for its copy alone.
    assert len(_verbs('label = "sign in, then sign in again"\n')) == 2
    page = 'PAGE = """<p>Hello</p>\n<p>Welcome back</p>\n<p>Sign&nbsp;in to continue</p>"""\n'
    assert [item.line for item in _verbs(page)] == [3]
    # Taking the tags out moves no line: not a tag that holds a line break, an inline one between the letters of the
    # word, an attribute on a later line or a decoded ``&#10;``.
    spread = 'PAGE = """<p>Hello</p>\n<a\n  href="/login">Log in</a>\n<p><strong>Sign</strong>\n in to go on</p>"""\n'
    assert [item.line for item in _verbs(spread)] == [4]
    assert [item.line for item in _verbs('PAGE = """<p>Sig<b\n>n in</p>"""\n')] == [1]
    assert [item.line for item in _verbs('PAGE = """<p>Hi</p>\n<img src="/a.png"\n     alt="Sign in">"""\n')] == [3]
    assert [item.line for item in _verbs('PAGE = """&#10;Sign in\nbye"""\n')] == [1]
    # The noun as the verb is a break of its own rule, on the line the noun is on, once for each place.
    assert [item.rule for item in _verbs('label = "Please login again."\n')] == ["account verb 'login' as a verb"]
    assert [item.line for item in _verbs('PAGE = """Please\nlogin again."""\n')] == [2]
    assert len(_verbs('label = "Please login, then login again."\n')) == 2
    model = 'RULE = "Never tell the reader to sign in."\nraise HTTPException(401, "Sign in again.")\n'
    assert [item.text for item in _verbs(model, "app/services/ai/summary_prompt.py")] == ["Sign in again."]
    assert len(_verbs(model, "app/services/ai/summary_writer.py")) == 2


def test_the_walk_reads_the_backend():
    files = scanned_files()
    copy = sum(read_module((BACKEND_DIR / rel).read_text(encoding="utf-8"), rel)[1] for rel in files)
    assert len(files) > 200 and copy > 1200, f"{len(files)} files, {copy} copy literals: the walk lost its reach"


def test_backend_copy_keeps_the_voice_outside_exempt():
    loose, _ = _breaks_by_entry()
    assert not loose, (
        "User-facing backend copy breaks the voice or token rules (docs/brand/07-voice.md): use a comma, "
        "a colon, a middot or a new sentence for an em-dash, a full stop for '!', no emoji, sentence-case "
        "headings, and token colours. Fix the line; EXEMPT only shrinks.\n" + "\n".join(map(str, loose))
    )


def test_every_exempt_entry_still_covers_a_break():
    _, covered = _breaks_by_entry()
    stale = [entry for entry, items in covered.items() if not items]
    assert not stale, f"These entries no longer break anything: delete them and lower EXEMPT_CAP: {stale}"


def test_each_exempt_entry_covers_exactly_its_breaks():
    # An entry exempts the breaks it counts, not its file: a new break in an exempt file fails here as it
    # would in any other, and a fix lowers the count in the same diff (an equality, as D-040 holds every cap).
    _, covered = _breaks_by_entry()
    moved = [
        f"{entry}: {len(covered[entry])} breaks, EXEMPT counts {count}"
        + "".join(f"\n  {item}" for item in covered[entry] if len(covered[entry]) > count)
        for entry, (count, _owner) in EXEMPT.items()
        if len(covered[entry]) != count
    ]
    assert not moved, (
        "An exempt entry's breaks changed: fix a new break as you would outside EXEMPT, and lower the count "
        "with each fix in the same diff (EXEMPT only shrinks).\n" + "\n".join(moved)
    )


def test_exempt_only_shrinks():
    # An equality, as D-040 holds every cap and the twin holds UNSOURCED_MAX: a ceiling would let a deletion
    # leave the cap where it was, and a later entry would then fit under it with no change to this line.
    assert len(EXEMPT) == EXEMPT_CAP, (
        f"EXEMPT has {len(EXEMPT)} entries and EXEMPT_CAP is {EXEMPT_CAP}: lower the cap with each deletion "
        "in the same diff, and never raise it for new copy (fix the copy instead of exempting it)"
    )
