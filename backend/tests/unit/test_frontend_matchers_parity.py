"""Backend twin of frontend/tests/unit/backendMessageMatches.spec.ts (decisions-log D-031 and D-036).

The frontend picks some UI by the words of a backend message: the Upgrade link instead of Retry on the
Copilot rail and the analysis page, the summary paywall card, the verify-your-email prompt that
lib/api/client.ts opens. Until an error code replaces the matching (tasks/todo.md), a copy edit on either
side can switch that UI off. The frontend spec holds both sides, but only in the frontend job; this test
runs the same tables in pytest, so a backend-only edit fails the local backend gate (ruff, bandit, pytest)
before it reaches CI. It follows backendMessageMatches.spec.ts (on main since #1288), clause 3 holding the
two equal, and reads the way that spec reads: docstrings skipped, every literal test inside a matcher
function a phrase (a block body or an expression body), a .tsx matcher read with its JSX tags.

1. Every phrase a MATCHERS function tests for occurs in a string literal of a file that writes the
   message, unless UNSOURCED lists it with its reason (shrink-only; its size equals UNSOURCED_MAX). This
   is the spec's first clause with the same MATCHERS, BACKEND and UNSOURCED tables; the phrases are read
   from the TypeScript source with comments, strings, regex literals and (in a .tsx file) JSX tags
   tokenised, so a commented-out test reads as nothing.
2. Each message in ROUTED, a backend site whose words a matcher has to catch, carries at least one of that
   matcher's phrases, with module constants such as ``_UPGRADE_HINT`` interpolated. The spec cannot see
   this case: when dependencies.py stops saying "Upgrade to Pro", analysis.py and summaries.py still write
   the phrase, so clause 1 stays green while the Copilot rail's taste-exhausted detail routes to Retry.
3. The spec's MATCHERS and BACKEND tables, its UNSOURCED keys and reasons and its UNSOURCED_MAX equal
   these, so the twins cannot drift; a spec moved or gone fails this case rather than skipping it.
"""
import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "frontend"
SPEC = FRONTEND / "tests" / "unit" / "backendMessageMatches.spec.ts"

BACKEND = {
    "dependencies": "backend/app/dependencies.py",
    "admission": "backend/app/services/summary_stages/admission.py",
    "summaries": "backend/app/routers/summaries.py",
    "analysis": "backend/app/routers/analysis.py",
    "subscriptions": "backend/app/routers/subscriptions.py",
}


@dataclass(frozen=True)
class Matcher:
    """A frontend matcher (``fn`` in ``file``; no ``fn``: every regex ``.test()`` in the module) and the files
    that write the messages it reads: repo-relative backend modules, frontend-relative fallbacks."""

    file: str
    fn: Optional[str]
    backend: tuple[str, ...]
    frontend: tuple[str, ...]


MATCHERS = (
    Matcher("features/summaries/api/summaries-api.ts", "isPaywallStreamError",
            (BACKEND["admission"], BACKEND["dependencies"], BACKEND["summaries"]), ()),
    Matcher("features/summaries/api/summaries-api.ts", "isNonRetryableStreamError",
            (BACKEND["summaries"], BACKEND["admission"]), ("features/summaries/api/summaries-api.ts",)),
    Matcher("features/filings/api/copilot-api.ts", "isCopilotFairUseLimit",
            (BACKEND["summaries"],), ("features/filings/api/copilot-api.ts",)),
    Matcher("features/filings/api/copilot-api.ts", "isCopilotPaywallError",
            (BACKEND["dependencies"], BACKEND["summaries"]), ("features/filings/api/copilot-api.ts",)),
    Matcher("features/analysis/api/analysis-api.ts", "isAnalysisPaywallError",
            (BACKEND["dependencies"], BACKEND["analysis"]), ("features/analysis/api/analysis-api.ts",)),
    Matcher("lib/api/client.ts", None, (BACKEND["subscriptions"],), ()),
    # The spec's tree-wide pass reaches this one (a test on error.message). The dashboard's error boundary
    # lists no source: auth.py's and client.ts's "/api/auth/..." paths would pass "auth" on a URL, not a
    # message. ContactForm.tsx left the table when #1303 read the contact form's rate limit from the status.
    Matcher("app/dashboard/error.tsx", "DashboardError", (), ()),
)

# Phrases no file writes today, each with its reason (the spec's table, keys and reasons word for word;
# clause 3 compares both). Shrink-only: delete the line and lower UNSOURCED_MAX in the same commit.
_DASHBOARD_UNSOURCED = (
    "no message that reaches the dashboard's error boundary says it (see MATCHERS); the redirect's logic is "
    "E31's (a status or an error code), never the brand sweep's"
)
UNSOURCED = {
    "DashboardError 401": _DASHBOARD_UNSOURCED,
    "DashboardError Unauthorized": _DASHBOARD_UNSOURCED,
    "DashboardError authentication": _DASHBOARD_UNSOURCED,
    "DashboardError auth": _DASHBOARD_UNSOURCED,
}
# Seeded at 2 when the spec scanned the api modules; 7 when its scan reached app/dashboard/error.tsx and
# ContactForm.tsx; 6 since #1303 read the contact form's rate limit from the status; 5 since #1293's 401
# fallback wrote "Sign in again to generate this summary.", a source for "sign in"; 4 since #1295 dropped
# "monthly cap" from isCopilotPaywallError, whose fair-use 429 isCopilotFairUseLimit reads. It only falls after.
UNSOURCED_MAX = 4


@dataclass(frozen=True)
class Routed:
    """A backend site whose message a matcher must recognise: the details of ``HTTPException`` calls with
    ``status`` inside ``function`` (nested functions included), or its ``return`` values."""

    module: str
    function: str
    status: object  # an HTTP status code, or "return"
    matcher: str  # a MATCHERS fn, or the file of a matcher without one


# The analysis route's fair-use 429 left this table when #1299 took "fair-use limit" out of
# isAnalysisPaywallError: a Pro user's monthly cap is stated in the narrative card with no plan link. The
# Copilot route's fair-use 429 is routed by its words (isCopilotFairUseLimit, #1295), so it is held here:
# clause 1 alone stays green on a reword of that detail while another literal in summaries.py, a log line
# say, still writes "fair-use limit", and a Pro user at the cap would get Retry instead of the plan card.
ROUTED = (
    Routed(BACKEND["dependencies"], "copilot_taste_exhausted_detail", "return", "isCopilotPaywallError"),
    Routed(BACKEND["dependencies"], "require_entitlement", 403, "isAnalysisPaywallError"),
    Routed(BACKEND["summaries"], "ask_filing_stream", 429, "isCopilotFairUseLimit"),
    Routed(BACKEND["subscriptions"], "create_checkout_session", 403, "lib/api/client.ts"),
)

Reader = Callable[[str], str]


def _read_repo(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- TypeScript, tokenised


@dataclass(frozen=True)
class _Literal:
    kind: str  # "str" (a quoted string or a template without substitutions), "tpl", "re"
    text: str
    start: int
    end: int


# Never "<": "</" closes a JSX tag (``</Button>}``), and no regex literal follows a "<" in this codebase.
_REGEX_AFTER = set("(,=:[!&|?{};+-*%>~^")
_REGEX_KEYWORDS = ("return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0"}


def _unescape(raw: str) -> str:
    return re.sub(r"\\(.)", lambda m: _ESCAPES.get(m.group(1), m.group(1)), raw, flags=re.S)


def _ts_literals(source: str, tsx: bool = False) -> tuple[list[_Literal], str]:
    """The string, template and regex literals of TypeScript source, and the source with comments and literal
    bodies blanked (same length), so brace matching and call shapes can be read off the blanked text.

    In a .tsx file a "<" followed by a letter, "/" or ">" opens a tag (a type argument such as
    ``FormEvent<HTMLFormElement>`` reads the same way, harmlessly): until its ">" at the same brace depth, a
    "/" belongs to the tag (``</Button>``, ``<Icon />``) and never opens a regex. Tags nest through
    attribute braces (``action={<Button>Go</Button>}``), so the open ones are a stack. Attribute strings are string
    literals, as TypeScript parses them. A template's ``${...}`` counts its braces apart from the code's depth,
    so a template attribute (``className={`p ${x}`}``) leaves the tag closing at its own depth. JSX text is
    read as code; react/no-unescaped-entities keeps quotes out of it (``We&apos;ve``), so it opens no
    literal."""
    literals: list[_Literal] = []
    masked = list(source)
    n = len(source)
    depth, tags = 0, []  # code brace depth; the depths at which .tsx tags are open, innermost last

    def blank(start: int, end: int) -> None:
        for k in range(start, end):
            if masked[k] != "\n":
                masked[k] = " "

    i = 0
    while i < n:
        c, nxt = source[i], source[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            end = source.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
        elif c == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            end = n if end < 0 else end + 2
            blank(i, end)
            i = end
        elif c in "'\"`":
            j, parts, substituted = i + 1, [], False
            while j < n and source[j] != c:
                if source[j] == "\\":
                    parts.append(source[j:j + 2])
                    j += 2
                elif c == "`" and source.startswith("${", j):
                    nested, j = 1, j + 2  # the substitution's own braces, never the code's depth
                    while j < n and nested:
                        nested += {"{": 1, "}": -1}.get(source[j], 0)
                        j += 1
                    parts.append(" ")
                    substituted = True
                else:
                    parts.append(source[j])
                    j += 1
            literals.append(_Literal("tpl" if substituted else "str", _unescape("".join(parts)), i, j + 1))
            blank(i + 1, j)
            i = j + 1
        elif tags and depth == tags[-1] and c in "/>":
            if c == ">":
                tags.pop()
            i += 1
        elif c == "/" and _starts_regex("".join(masked[max(0, i - 30):i])):
            j, in_class = i + 1, False
            while j < n and source[j] != "\n" and (source[j] != "/" or in_class):
                if source[j] == "\\":
                    j += 1
                elif source[j] == "[":
                    in_class = True
                elif source[j] == "]":
                    in_class = False
                j += 1
            end = j + 1
            while end < n and source[end].isalpha():
                end += 1
            literals.append(_Literal("re", source[i + 1:j], i, end))
            blank(i + 1, j)
            i = end
        else:
            if tsx and c == "<" and (nxt.isalpha() or nxt in "/>"):
                tags.append(depth)
            elif c in "{}":
                depth += 1 if c == "{" else -1
            i += 1
    return literals, "".join(masked)


def _starts_regex(before: str) -> bool:
    """A "/" opens a regex literal after an operator, an opening bracket or a keyword; after a name, a
    number or a closing bracket it divides (``total / count``)."""
    before = before.rstrip()
    word = re.search(r"(\w+)$", before)
    return not before or before[-1] in _REGEX_AFTER or bool(word and word.group(1) in _REGEX_KEYWORDS)


# An expression goes on past a line break when its line ends on an operator or the next line starts with one
# (``||`` at either end, a ``.`` that chains a call, a ternary's ``?`` and ``:``). Never "/": a regex ends on it.
_GOES_ON_AFTER = tuple("|&?:+-*%=<>^~.")
_GOES_ON_BEFORE = tuple(".|&?:+-*%=<>^")


def _expression_end(masked: str, start: int) -> int:
    """The end of the expression body of an arrow function that starts at ``start``, as its statement ends: a
    ``;`` or ``,`` outside its own brackets, a bracket that closes one it did not open, or a line break the
    expression does not go on past.

    Limits, where the spec's TypeScript reader is right and this one is not (no matcher in MATCHERS has these
    shapes): a line that ends on a JSX closing tag's ``>`` or a postfix ``++`` or ``--`` reads as going on, so
    the next statement's test is read as the matcher's; a next line that opens with ``[`` or a line break
    inside a template literal outside any bracket ends the body, so the phrases after it are dropped."""
    depth = 0
    for i in range(start, len(masked)):
        c = masked[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif depth == 0 and (c in ";," or (
            c == "\n"
            and not masked[start:i].rstrip().endswith(_GOES_ON_AFTER)
            and not masked[i:].lstrip().startswith(_GOES_ON_BEFORE)
        )):
            return i
    return len(masked)


def _function_span(masked: str, name: str) -> tuple[int, int]:
    """The block body of ``function name`` or ``const name = (...) => {``, or the expression body of
    ``const name = (...) => expr`` (isCopilotFairUseLimit's shape), in the blanked source."""
    found = re.search(rf"\b(?:function\s+{name}\b|(?:const|let|var)\s+{name}\s*(?::[^=]*)?=)", masked)
    if not found:
        raise AssertionError(f"{name} is gone; update MATCHERS")
    depth, i = 0, found.end()
    while i < len(masked) and not (depth == 0 and masked[i] == "{"):
        if depth == 0 and masked.startswith("=>", i):
            i += 2
            while i < len(masked) and masked[i].isspace():
                i += 1
            if i < len(masked) and masked[i] == "{":
                break
            return i, _expression_end(masked, i)
        depth += {"(": 1, "[": 1, ")": -1, "]": -1}.get(masked[i], 0)
        i += 1
    if i >= len(masked):
        raise AssertionError(f"{name}: no function body")
    start, depth = i, 0
    for j in range(i, len(masked)):
        depth += {"{": 1, "}": -1}.get(masked[j], 0)
        if depth == 0:
            return start, j + 1
    raise AssertionError(f"{name}: unbalanced braces")


def _literal_tests(literals: list[_Literal], masked: str) -> Iterator[tuple[_Literal, str]]:
    """Each literal test, as in the spec: ``x.includes('…')`` (or startsWith, endsWith), ``x.match(/…/)``
    (or search) and ``/…/.test(x)``."""
    for literal in literals:
        before = masked[max(0, literal.start - 40):literal.start]
        if literal.kind == "str":
            call = re.search(r"\.(includes|startsWith|endsWith)\(\s*$", before)
            if call:
                yield literal, call.group(1)
        elif literal.kind == "re":
            call = re.search(r"\.(match|search)\(\s*$", before)
            if call:
                yield literal, call.group(1)
            elif re.match(r"\s*\.test\(", masked[literal.end:literal.end + 20]):
                yield literal, "test"


@dataclass(frozen=True)
class Phrase:
    text: str
    regex: bool

    def found_in(self, text: str) -> bool:
        if self.regex:
            return re.search(self.text, text, re.IGNORECASE) is not None
        return self.text.lower() in text.lower()


def phrases(matcher: Matcher, read: Reader = _read_repo) -> list[Phrase]:
    """The phrases a matcher tests for (with a function: every literal test in it, includes, startsWith,
    endsWith and regex alike; without: the module's regex ``.test()`` calls), as the spec reads them."""
    literals, masked = _ts_literals(read(f"frontend/{matcher.file}"), matcher.file.endswith(".tsx"))
    span = _function_span(masked, matcher.fn) if matcher.fn else (0, len(masked))
    out: list[Phrase] = []
    for literal, kind in _literal_tests(literals, masked):
        if not span[0] <= literal.start < span[1]:
            continue
        if matcher.fn or kind == "test":
            out.append(Phrase(literal.text, literal.kind == "re"))
    return out


def frontend_strings(file: str, read: Reader = _read_repo) -> list[str]:
    """The string literals a frontend fallback module writes, its own literal tests excluded."""
    literals, masked = _ts_literals(read(f"frontend/{file}"), file.endswith(".tsx"))
    tests = {id(literal) for literal, _ in _literal_tests(literals, masked)}
    return [literal.text for literal in literals if literal.kind in ("str", "tpl") and id(literal) not in tests]


# --------------------------------------------------------------------------- Python


def _module_constants(tree: ast.Module) -> dict[str, ast.expr]:
    constants: dict[str, ast.expr] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            constants[stmt.targets[0].id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            constants[stmt.target.id] = stmt.value
    return constants


def _docstrings(tree: ast.Module) -> set[int]:
    """The literal that opens the first statement of the module or of a ``def`` or ``class`` body, as the
    spec's pythonStrings skips it: it documents the code, it is never a message."""
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, (ast.Constant, ast.JoinedStr)):
                skip.add(id(first.value))
    return skip


def python_strings(source: str) -> list[str]:
    """Every string literal in a module (adjacent literals already joined by the parser; an f-string's
    interpolations read as ``{}``), docstrings skipped, as the spec's pythonStrings reads them."""
    tree = ast.parse(source)
    parts = {id(part) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for part in node.values}
    skip = _docstrings(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in parts:
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            out.append("".join(part.value if isinstance(part, ast.Constant) else "{}" for part in node.values))
    return out


def _renderings(expr: Optional[ast.AST], names: dict[str, ast.expr], seen: frozenset[str] = frozenset()) -> list[str]:
    """Every text an expression can render to, names resolved through ``names`` (module constants and the
    function's own assignments); anything unknown reads as ``{}``."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return [expr.value]
    if isinstance(expr, ast.JoinedStr):
        texts = [""]
        for part in expr.values:
            options = [part.value] if isinstance(part, ast.Constant) else _renderings(part.value, names, seen)
            texts = [text + option for text in texts for option in options]
        return texts
    if isinstance(expr, ast.IfExp):
        return _renderings(expr.body, names, seen) + _renderings(expr.orelse, names, seen)
    if isinstance(expr, ast.BoolOp):
        return [text for value in expr.values for text in _renderings(value, names, seen)]
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return [a + b for a in _renderings(expr.left, names, seen) for b in _renderings(expr.right, names, seen)]
    if isinstance(expr, ast.Name) and expr.id in names and expr.id not in seen:
        return _renderings(names[expr.id], names, seen | {expr.id})
    return ["{}"]


def _status(call: ast.Call) -> Optional[int]:
    value = next((k.value for k in call.keywords if k.arg == "status_code"), call.args[0] if call.args else None)
    if isinstance(value, ast.Constant) and isinstance(value.value, int):
        return value.value
    if isinstance(value, ast.Attribute):
        code = re.match(r"HTTP_(\d{3})_", value.attr)
        return int(code.group(1)) if code else None
    return None


def routed_messages(site: Routed, read: Reader = _read_repo) -> list[tuple[int, str]]:
    """(line, text) for each message a ROUTED site can send."""
    tree = ast.parse(read(site.module))
    function = next(
        (node for node in ast.walk(tree)
         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == site.function),
        None,
    )
    if function is None:
        raise AssertionError(f"{site.module}: {site.function} is gone; update ROUTED")
    names = _module_constants(tree)
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            names[node.targets[0].id] = node.value
    messages: list[tuple[int, str]] = []
    for node in ast.walk(function):
        if site.status == "return" and isinstance(node, ast.Return) and node.value is not None:
            messages += [(node.lineno, text) for text in _renderings(node.value, names)]
        elif isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "HTTPException":
            if _status(node) == site.status:
                detail = next((k.value for k in node.keywords if k.arg == "detail"), node.args[1] if len(node.args) > 1 else None)
                messages += [(node.lineno, text) for text in _renderings(detail, names)]
    return messages


# --------------------------------------------------------------------------- the clauses


def _matcher_key(matcher: Matcher) -> str:
    return matcher.fn or matcher.file


def unsourced(read: Reader = _read_repo) -> tuple[list[str], set[str]]:
    """(phrases nobody writes that UNSOURCED does not list, UNSOURCED keys still in use)."""
    missing: list[str] = []
    used: set[str] = set()
    for matcher in MATCHERS:
        strings = [s for path in matcher.backend for s in python_strings(read(path))]
        strings += [s for file in matcher.frontend for s in frontend_strings(file, read)]
        for phrase in phrases(matcher, read):
            if any(phrase.found_in(s) for s in strings):
                continue
            key = f"{_matcher_key(matcher)} {phrase.text}"
            if key in UNSOURCED:
                used.add(key)
            else:
                writers = ", ".join(matcher.backend + matcher.frontend)
                missing.append(f'{matcher.file} {matcher.fn or ""} tests for "{phrase.text}", which none of {writers} writes')
    return missing, used


def unrouted(read: Reader = _read_repo) -> list[str]:
    """ROUTED messages that carry none of their matcher's phrases."""
    by_key = {_matcher_key(matcher): matcher for matcher in MATCHERS}
    failures: list[str] = []
    for site in ROUTED:
        words = phrases(by_key[site.matcher], read)
        messages = routed_messages(site, read)
        if not messages:
            failures.append(f"{site.module} {site.function}: no {site.status} message found; update ROUTED")
        for line, text in messages:
            if not any(phrase.found_in(text) for phrase in words):
                failures.append(
                    f"{site.module}:{line} ({site.function}) {text!r} carries none of {site.matcher}'s words "
                    f"{[phrase.text for phrase in words]}"
                )
    return failures


def test_the_readers_see_what_the_spec_sees():
    for matcher in MATCHERS:
        assert phrases(matcher), f"{matcher.file} {matcher.fn or 'regex tests'}: the reader found no phrase"
    for site in ROUTED:
        assert routed_messages(site), f"{site.module} {site.function}: no message"

    probe = """
// m.includes('commented out')
const URL = 'http://x' // a "//" inside a string is not a comment
const ratio = total / count
export const isProbeError = (message: string): boolean => {
  const m = (message || '').toLowerCase()
  /* m.includes('blocked') */
  return m.includes('pro feature') || /fair-use\\s+limit/i.test(m) || m.startsWith('data:')
}
const after = () => m.includes('outside')
const fallback = `Monthly limit ${n} reached`
"""
    files = {"frontend/probe.ts": probe}
    read = files.__getitem__
    matcher = Matcher("probe.ts", "isProbeError", (), ())
    assert phrases(matcher, read) == [
        Phrase("pro feature", False), Phrase("fair-use\\s+limit", True), Phrase("data:", False),
    ]
    assert frontend_strings("probe.ts", read) == ["http://x", "", "Monthly limit   reached"]
    assert python_strings('x = ("a "  # note\n     f"b {y}")\n# "not a string"\n') == ["a b {}"]
    # Docstrings document code, never a message; a literal that opens any other statement is kept (the
    # spec's own probe, line for line).
    docstrings = "\n".join([
        '"""Module docstring: sign in."""',
        "class Gate(Base):",
        '    """Class docstring."""',
        "    async def check(",
        "        self, user: User,",
        "    ) -> None:",
        "        '''Method docstring.'''",
        '        raise HTTPException(status_code=401, detail="Please sign in.")',
        "def bare():",
        '    "Function docstring."',
        '"""A later bare literal is no docstring."""',
    ])
    assert sorted(python_strings(docstrings)) == ["A later bare literal is no docstring.", "Please sign in."]

    # A .tsx matcher: "</" closes a tag and "/>" ends one, never a regex, so the braces after them still
    # count and the phrases after the JSX stay inside the function; a type argument reads as a tag,
    # harmlessly, and a comparison "<" is not one.
    tsx = """
export default function ProbeError({ error }: { error: Error }) {
  const [state] = useState<string | null>(null)
  const ok = items.length < 10 && /sign\\s+in/i.test(error.message)
  const card = (
    <Panel>
      {ok && <Card
        action={<Button onClick={() => go('/login')}>Go to Login</Button>}
        icon={<Icon className="h-5 w-5" />}
        extra={<>{state}</>} />}
    </Panel>
  )
  const isAuthError = error.message.includes('401') || error.message.toLowerCase().includes('auth')
  return <p>We&apos;ve logged it.</p>
}
const after = () => error.message.includes('outside')
"""
    read_tsx = {"frontend/probe.tsx": tsx}.__getitem__
    assert phrases(Matcher("probe.tsx", "ProbeError", (), ()), read_tsx) == [
        Phrase("sign\\s+in", True), Phrase("401", False), Phrase("auth", False),
    ]
    # A template attribute before a regex test (the review of cd0d38cd): the substitution's braces are its
    # own, so the tag closes at the code's depth and the "/" of the regex two blocks down still opens it.
    templated = """
export default function TemplateProbe({ error }: { error: Error }) {
  const badge = <span className={`p ${x}`}>Error</span>
  useEffect(() => {
    if (error) {
      setAuth(error.message.includes('401') || /sign\\s+in/i.test(error.message))
    }
  }, [error])
  return badge
}
"""
    read_templated = {"frontend/templated.tsx": templated}.__getitem__
    assert phrases(Matcher("templated.tsx", "TemplateProbe", (), ()), read_templated) == [
        Phrase("401", False), Phrase("sign\\s+in", True),
    ]
    # An expression body (isCopilotFairUseLimit's shape, #1295) runs to the line break the expression does not
    # go on past: an operator ending a line or starting the next keeps the chain in, and the next statement's
    # test stays out.
    arrows = """
export const isProbeLimit = (message: string): boolean =>
  (message || '').toLowerCase().includes('fair-use limit')

const isProbeChain = (m: string): boolean =>
  m.includes('first') ||
  m.includes('second')
  || /third/i.test(m)
const isProbeTernary = (m: string): boolean =>
  m.startsWith('x')
    ? m.includes('yes')
    : /no/i.test(m)
const isProbeDots = (m: string): boolean =>
  (m || '')
    .toLowerCase()
    .includes('dotted')
const after = () => m.includes('outside')
"""
    read_arrows = {"frontend/arrows.ts": arrows}.__getitem__
    assert phrases(Matcher("arrows.ts", "isProbeLimit", (), ()), read_arrows) == [Phrase("fair-use limit", False)]
    assert phrases(Matcher("arrows.ts", "isProbeChain", (), ()), read_arrows) == [
        Phrase("first", False), Phrase("second", False), Phrase("third", True),
    ]
    # A ternary's ? and : and a chain's leading . go on past their line break as || does.
    assert phrases(Matcher("arrows.ts", "isProbeTernary", (), ()), read_arrows) == [
        Phrase("x", False), Phrase("yes", False), Phrase("no", True),
    ]
    assert phrases(Matcher("arrows.ts", "isProbeDots", (), ()), read_arrows) == [Phrase("dotted", False)]
    dashboard = next(m for m in MATCHERS if m.fn == "DashboardError")
    assert [phrase.text for phrase in phrases(dashboard)] == ["401", "Unauthorized", "authentication", "auth"]


def test_every_phrase_the_frontend_routes_on_is_written():
    missing, used = unsourced()
    assert not missing, "Keep the phrase in the message (backend and frontend together), or change the matcher:\n" + "\n".join(missing)
    # Equality, as the spec holds it: a PR that shrinks the list lowers the cap in the same commit.
    assert len(UNSOURCED) == UNSOURCED_MAX, (
        f"UNSOURCED changed size ({len(UNSOURCED)}, UNSOURCED_MAX {UNSOURCED_MAX}): move UNSOURCED_MAX with it in the same commit"
    )
    stale = sorted(set(UNSOURCED) - used)
    assert not stale, f"Written again or gone from its matcher: delete it from UNSOURCED: {stale}"


def test_each_routed_backend_message_carries_its_matchers_words():
    failures = unrouted()
    assert not failures, "A routed message lost the words its matcher reads:\n" + "\n".join(failures)


def test_a_reword_in_one_module_fails_even_while_another_still_writes_the_phrase():
    """dependencies.py with "Upgrade to Pro" reworded, in a copied fixture: clause 1 stays green (analysis.py
    and summaries.py still write the phrase), clause 2 names the taste-exhausted detail."""
    original = _read_repo(BACKEND["dependencies"])
    assert "Upgrade to Pro" in original, "the fixture's precondition: dependencies.py says Upgrade to Pro"
    reworded = {BACKEND["dependencies"]: original.replace("Upgrade to Pro", "Go Pro")}

    def read(path: str) -> str:
        return reworded.get(path) or _read_repo(path)

    assert unsourced(read)[0] == []
    failures = unrouted(read)
    assert failures and all("dependencies.py" in failure for failure in failures)
    assert any("copilot_taste_exhausted_detail" in failure and "upgrade to pro" in failure for failure in failures)


def _spec_tables(source: str) -> tuple[dict[str, str], set[Matcher], dict[str, str], Optional[int]]:
    """BACKEND, MATCHERS, UNSOURCED (key to reason, a named constant resolved) and UNSOURCED_MAX as the
    frontend spec declares them; unreadable fails loudly."""
    literals, masked = _ts_literals(source)

    def block(name: str, opener: str, closer: str) -> tuple[int, int]:
        found = re.search(rf"\bconst {name}\b[^=]*=\s*\{opener}", masked)
        assert found, f"backendMessageMatches.spec.ts: {name} is unreadable"
        depth = 0
        for j in range(found.end() - 1, len(masked)):
            depth += {opener: 1, closer: -1}.get(masked[j], 0)
            if depth == 0:
                return found.end(), j
        raise AssertionError(f"backendMessageMatches.spec.ts: {name} never closes")

    def strings_in(start: int, end: int) -> list[_Literal]:
        return [literal for literal in literals if start <= literal.start < end and literal.kind == "str"]

    start, end = block("BACKEND", "{", "}")
    keys = re.findall(r"(\w+)\s*:", masked[start:end])
    values = [literal.text for literal in strings_in(start, end)]
    assert keys and len(keys) == len(values), "backendMessageMatches.spec.ts: BACKEND is unreadable"
    backend = dict(zip(keys, values))

    start, end = block("MATCHERS", "[", "]")
    matchers: set[Matcher] = set()
    for entry in re.finditer(r"\{[^{}]*\}", masked[start:end]):
        a, b = start + entry.start(), start + entry.end()
        text, fields = masked[a:b], {}
        for field in ("file", "fn"):
            spot = re.search(rf"\b{field}\s*:\s*['\"]", text)
            fields[field] = next((lit.text for lit in strings_in(a + spot.end() - 1, b)), None) if spot else None
        lists = {}
        for field in ("backend", "frontend"):
            spot = re.search(rf"\b{field}\s*:\s*\[([^\]]*)\]", text)
            assert spot, f"backendMessageMatches.spec.ts: MATCHERS entry without {field}"
            items = [backend[key] for key in re.findall(r"BACKEND\.(\w+)", spot.group(1))]
            items += [lit.text for lit in strings_in(a + spot.start(1), a + spot.end(1))]
            lists[field] = tuple(sorted(items))
        matchers.add(Matcher(fields["file"], fields["fn"], lists["backend"], lists["frontend"]))
    assert matchers, "backendMessageMatches.spec.ts: MATCHERS is unreadable"

    def literal_at(at: int, what: str) -> _Literal:
        found = next((lit for lit in literals if lit.start == at and lit.kind == "str"), None)
        assert found, f"backendMessageMatches.spec.ts: {what} is not a string literal"
        return found

    start, end = block("UNSOURCED", "{", "}")
    reasons: dict[str, str] = {}
    for key in strings_in(start, end):
        colon = re.match(r"\s*:\s*", masked[key.end:end])
        if not colon:
            continue  # a reason, not a key
        at = key.end + colon.end()
        name = re.match(r"[A-Za-z_]\w*", masked[at:end])
        if name:  # a reason shared through a constant (DASHBOARD_UNSOURCED)
            const = re.search(rf"\bconst {name.group(0)}\s*(?::[^=]*)?=\s*", masked)
            assert const, f"backendMessageMatches.spec.ts: UNSOURCED names {name.group(0)}, which is unreadable"
            reason = literal_at(const.end(), name.group(0))
            after = at + name.end()
        else:
            reason = literal_at(at, f"UNSOURCED[{key.text!r}]")
            after = reason.end
        assert re.match(r"\s*(?:,|$)", masked[after:end]), f"backendMessageMatches.spec.ts: UNSOURCED[{key.text!r}] is unreadable"
        reasons[key.text] = reason.text
    cap = re.search(r"\bconst UNSOURCED_MAX\s*=\s*(\d+)", masked)
    return backend, matchers, reasons, int(cap.group(1)) if cap else None


def test_the_twins_share_their_tables():
    # The spec is on main since #1288, so a missing one is a move or a deletion, never a reason to skip.
    assert SPEC.exists(), f"{SPEC.relative_to(REPO)} is gone or moved: point SPEC at the spec this twin follows"
    backend, matchers, reasons, cap = _spec_tables(SPEC.read_text(encoding="utf-8"))
    ours = {Matcher(m.file, m.fn, tuple(sorted(m.backend)), tuple(sorted(m.frontend))) for m in MATCHERS}
    assert backend == BACKEND, "BACKEND differs from the frontend spec's"
    assert matchers == ours, f"MATCHERS differs from the frontend spec's:\nspec only {matchers - ours}\nhere only {ours - matchers}"
    assert set(reasons) == set(UNSOURCED), (
        f"UNSOURCED differs from the frontend spec's: spec only {sorted(set(reasons) - set(UNSOURCED))}, "
        f"here only {sorted(set(UNSOURCED) - set(reasons))}"
    )
    reworded = sorted(key for key in UNSOURCED if reasons[key] != UNSOURCED[key])
    assert not reworded, f"UNSOURCED reasons differ from the frontend spec's: {reworded}"
    assert cap == UNSOURCED_MAX, f"UNSOURCED_MAX differs from the frontend spec's ({cap})"
