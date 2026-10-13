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
   (``RECOVERY_SYSTEM_MESSAGE``, ``build_system_message``);
4. a module constant that one of the above names (``detail=SOME_CONSTANT``);
5. HTML markup, wherever it sits (a closing tag, or a known element whose attributes carry values):
   mail and PDF bodies;
6. any literal of a DOCUMENT_MODULES file, whose strings are the text of a mail, a PDF, a CSV, a
   workbook or the summary's own fallback markdown.

Never read as copy: docstrings, the arguments of logging calls and ``print``, and patterns handed to ``re``.

Checks on that copy: an em-dash (the bare null token ``"—"`` excepted); an exclamation mark (``!=``,
HTML comments and ``!important`` excepted); an emoji or dingbat; an <h1>/<h2> in Title Case. The retired
colours (RETIRED_HEX) are checked in every literal of the scanned files except docstrings and log
arguments, since a hex string is only ever a colour.

EXEMPT lists what breaks today, each entry with the PR or decision that owns its fix: a file, or
``file::function`` for half of one. It only shrinks: an entry that no longer covers a break fails as
stale, and EXEMPT_CAP (the count when this gate landed) fails an addition. Delete an entry when its
owner lands, lower EXEMPT_CAP in the same diff, never raise it. Keep the blank line between owner
groups so two PRs shrinking different groups merge cleanly.

Limits (review, not this walk): copy assembled outside these six shapes in a module that is not a
document module, such as a positional constructor argument, a list element or a local without a role
word handed on by name (``x = "..."`` then ``detail=x``; two such strings carry
an em-dash today: the ADS-ratio sources in edgar/ads_ratios.py and the issuer cash-flow table header in
ai/issuer_cash_disclosure.py); casing below <h2>; and claims, which brandCopyRules.spec.ts reads.
"""
import ast
import html
import re
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
ROLE_NAME = re.compile(
    r"(?:^|_)(?:detail|message|msg|error|hint|footer|title|headline|subject|html|caption|disclaimer|notice|excerpt)$",
    re.IGNORECASE,
)
# A role name that also says the text is for the model is a prompt part, not copy (RECOVERY_SYSTEM_MESSAGE).
MODEL_FACING_NAME = re.compile(r"system|prompt|schema|instruction", re.IGNORECASE)
LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})

EM_DASH = "\u2014"
NOT_A_BANG = re.compile(r"!=|<!--|<!\[(?:if|endif|CDATA)|<!doctype|!important", re.IGNORECASE)
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

# What breaks today, grouped by the PR or decision that owns the fix. Shrink-only (module docstring).
EXEMPT: dict[str, str] = {
    "app/routers/auth.py": "founder: the auth router's details wait for the go-ahead",
    "app/services/ai/markdown_render.py": "founder: eval-pinned summary fallback text",
    "app/services/ai/summary_finalize.py": "founder: the pipeline's 'Unable to retrieve' sentence (failure.py routes on it)",
    "app/services/summary_stages/admission.py": "founder: summary pipeline sentences",
    "app/services/summary_stages/failure.py": "founder: summary pipeline sentences",
    "app/services/summary_stages/fetch.py": "founder: summary pipeline sentences",

    "app/routers/contact.py::send_contact_notifications": "backend-mail-templates",
    "app/routers/feedback.py::_notify_admin": "backend-mail-templates",
    "app/services/email_service.py": "backend-mail-templates",

    "app/services/analysis_export_metadata.py": "backend-exports",
    "app/services/excel_export_service.py": "backend-exports",
    "app/services/export_service.py": "backend-exports",
    "app/services/pdf_branding.py": "backend-exports",

    "app/services/fallback_summary.py": "backend-copy-high",
    "app/services/summary_sections.py": "backend-copy-high",

    "app/routers/email.py::send_test_email": "no owner yet: the admin-only Resend test mail",
    "app/services/trend_analysis/citations.py": "no owner yet: the analysis citation's derived-Q4 label",
    "app/services/trend_analysis/detectors.py": "no owner yet: the cash-conversion red flag",
}
# The entry count when the gate landed. Lower it with every deletion (two shrinking PRs that conflict
# on this line keep the smaller number); raising it is the one change this gate exists to refuse.
EXEMPT_CAP = 18


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


class _Reader(ast.NodeVisitor):
    """Collect the literals of one module, which of them reach a user, and each literal's scope."""

    def __init__(self, tree: ast.Module) -> None:
        self.constants: dict[str, ast.expr] = {}
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                self.constants[stmt.targets[0].id] = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
                self.constants[stmt.target.id] = stmt.value
        self.skip = self._skipped(tree)
        self.reached: set[int] = set()
        self.literals: list[tuple[ast.AST, str]] = []
        self._scope: list[str] = []
        self._functions: list[str] = []
        self.visit(tree)

    @staticmethod
    def _skipped(tree: ast.Module) -> set[int]:
        """Docstrings, and everything inside a logging, print or ``re`` call."""
        skip: set[int] = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body:
                first = body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                    skip.add(id(first.value))
            if isinstance(node, ast.Call) and _is_log_or_pattern(node):
                skip.update(id(sub) for sub in ast.walk(node))
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
        if self._functions and _names_copy(self._functions[-1]):
            self._reach(node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        for keyword in node.keywords:
            if keyword.arg in COPY_KEYWORDS or keyword.arg == "content":
                self._reach(keyword.value)
        if _call_name(node) == "HTTPException" and len(node.args) >= 2:
            self._reach(node.args[1])
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value in COPY_KEYS:
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


def _call_name(node: ast.Call) -> str:
    func = node.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""


def _is_log_or_pattern(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    if not isinstance(func, ast.Attribute):
        return False
    owner = func.value.id if isinstance(func.value, ast.Name) else func.value.attr if isinstance(func.value, ast.Attribute) else ""
    return owner == "re" or (func.attr in LOG_METHODS and "log" in owner.lower())


def read_module(source: str, path: str) -> tuple[list[Break], int]:
    """(breaks, copy literals read) for one module; ``path`` (relative to backend/) sets the document mode."""
    reader = _Reader(ast.parse(source))
    found: list[Break] = []
    copy = 0
    for node, scope in reader.literals:
        text = _text(node)
        if path in DOCUMENT_MODULES or id(node) in reader.reached or MARKUP.search(text):
            copy += 1
            for offset, rule in _copy_breaks(text):
                found.append(Break(path, node.lineno + text.count("\n", 0, offset), scope, rule, text.strip()))
        for colour in RETIRED_HEX.finditer(text):
            line = node.lineno + text.count("\n", 0, colour.start())
            found.append(Break(path, line, scope, f"retired colour {colour.group(0)}", text.strip()))
    return sorted(set(found), key=lambda b: (b.path, b.line, b.rule)), copy


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
    if n > 1:
        raise HTTPException(status_code=409, detail="This report is out of date — run it again.")
    run.message = "Hold on — joining."
    page = '<p style="color:#6B7280">Hi there</p><h2>Thank You for Writing</h2><h2>Welcome to EarningsNerd</h2>'
    fine = '<!-- note --><style>p {color: red !important}</style><p>a != b</p>'
    return JSONResponse(content={"success": False, "reason": "Oops — no", "message": "Saved ✨", "empty": "—"})


def taste_detail(n):
    def fallback():
        return "Inner — not a detail"
    return f"You have used {n} questions!"


def build_system_message(n):
    return "Plan — answer as JSON!"
'''

_PAGE = '<p style="color:#6B7280">Hi there</p><h2>Thank You for Writing</h2><h2>Welcome to EarningsNerd</h2>'
_PROBE_BREAKS = {
    ("exclamation mark", "Slow down!"),
    ("em-dash", "Too many requests — wait a minute."),
    ("retired colour #333", "#333"),
    ("em-dash", "{} items — retry"),
    ("exclamation mark", "Gone!"),
    ("em-dash", "This report is out of date — run it again."),
    ("em-dash", "Hold on — joining."),
    ("retired colour #6B7280", _PAGE),
    ("Title Case <h2>", _PAGE),
    ("em-dash", "Oops — no"),
    ("emoji", "Saved ✨"),
    ("exclamation mark", "You have used {} questions!"),
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
    }


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


def test_exempt_only_shrinks():
    assert len(EXEMPT) <= EXEMPT_CAP, (
        f"EXEMPT grew to {len(EXEMPT)} entries (cap {EXEMPT_CAP}): fix the copy instead of exempting it"
    )
