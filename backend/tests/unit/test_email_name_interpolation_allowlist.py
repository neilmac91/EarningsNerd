"""Structural gate: a recipient's name enters an email template ONLY through ``_greeting``.

Seven templates in ``app/services/email_service.py`` once wrote ``f"Hi {name},"`` straight into
HTML, and every sender appended the plain-text copy raw inside ``<pre style="display:none">``.
Both are now routed through helpers (``_greeting`` escapes and single-lines the name;
``_hidden_text`` escapes the text copy), and the rendering proof lives in
``test_email_name_escaping.py``. Prose alone would rot (CLAUDE.md rule 12), so this AST walk over
the module pins the shape:

- no f-string, ``+``/``%`` concatenation or ``.format(...)`` call anywhere in the module uses a
  bare ``name`` / ``full_name``;
- every ``greeting = ...`` assignment is a call to ``_greeting``;
- the hidden-copy literal (``display:none``) appears only inside ``_hidden_text``.

The result must equal the allow-list EXACTLY (today: empty). A new template that bypasses a
helper fails with a pointer to the fix; a site that is ever sanctioned must carry a written reason.
"""
import ast
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "app" / "services" / "email_service.py"

# (function, offence) pairs allowed to bypass the helpers. Empty: every template uses them.
ALLOWED_SITES: set[tuple[str, str]] = set()

NAME_IDS = {"name", "full_name"}
GREETING_HELPER = "_greeting"
HIDDEN_TEXT_HELPER = "_hidden_text"
HIDDEN_COPY_MARKER = "display:none"


def _bare_name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) and node.id in NAME_IDS else None


class _Finder(ast.NodeVisitor):
    """Collect (enclosing function, offence) for every way a name could reach a template raw."""

    def __init__(self) -> None:
        self.hits: list[tuple[str, str]] = []
        self._stack: list[str] = []

    def _where(self) -> str:
        return self._stack[-1] if self._stack else "<module>"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        for part in node.values:
            if isinstance(part, ast.FormattedValue) and (ident := _bare_name(part.value)):
                self.hits.append((self._where(), f"f-string interpolates {{{ident}}}"))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, (ast.Add, ast.Mod)):
            for side in (node.left, node.right):
                if ident := _bare_name(side):
                    self.hits.append((self._where(), f"string arithmetic on {ident}"))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            values = list(node.args) + [keyword.value for keyword in node.keywords]
            for value in values:
                if ident := _bare_name(value):
                    self.hits.append((self._where(), f".format() receives {ident}"))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(isinstance(target, ast.Name) and target.id == "greeting" for target in node.targets):
            value = node.value
            is_helper_call = (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == GREETING_HELPER
            )
            if not is_helper_call:
                self.hits.append((self._where(), f"greeting built without {GREETING_HELPER}()"))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and HIDDEN_COPY_MARKER in node.value and self._where() != HIDDEN_TEXT_HELPER:
            self.hits.append((self._where(), f"hidden text copy built without {HIDDEN_TEXT_HELPER}()"))


def _raw_name_sites(source: str) -> list[tuple[str, str]]:
    finder = _Finder()
    finder.visit(ast.parse(source))
    return finder.hits


# A gate that cannot fail proves nothing: pin what the finder catches and what it lets through.
_FINDER_PROBE = '''
import html

def _greeting(name):
    return f"Hi {html.escape(name)}," if name else "Hi there,"

def _hidden_text(text):
    return f'<pre style="display:none">{html.escape(text)}</pre>'

def raw_fstring(name):
    greeting = f"Hi {name}," if name else "Hi there,"
    return greeting

def escaped_inline(name):
    greeting = f"Hi {html.escape(name)}," if name else "Hi there,"
    return greeting

def concatenation(full_name):
    return "Hi " + full_name + ","

def percent_format(name):
    return "Hi %s," % name

def str_format(name):
    return "Hi {},".format(name)

def raw_hidden_copy(text):
    return f"<pre style=\\"display:none\\">{text}</pre>"

async def uses_helpers(name, text):
    greeting = _greeting(name)
    return f"<p>{greeting}</p>{_hidden_text(text)}"

def other_names_are_fine(company_name, ticker):
    return f"{company_name} ({ticker})" + ticker
'''


def test_finder_catches_every_bypass_shape_and_accepts_the_helpers():
    assert _raw_name_sites(_FINDER_PROBE) == [
        ("raw_fstring", "greeting built without _greeting()"),
        ("raw_fstring", "f-string interpolates {name}"),
        ("escaped_inline", "greeting built without _greeting()"),
        ("concatenation", "string arithmetic on full_name"),
        ("percent_format", "string arithmetic on name"),
        ("str_format", ".format() receives name"),
        ("raw_hidden_copy", "hidden text copy built without _hidden_text()"),
    ]


def test_email_service_routes_every_name_through_the_helpers():
    found = set(_raw_name_sites(MODULE.read_text(encoding="utf-8")))
    unexpected = found - ALLOWED_SITES
    assert not unexpected, (
        "app/services/email_service.py interpolates a recipient's name outside the escaping helpers:\n"
        + "\n".join(f"  {function}(): {offence}" for function, offence in sorted(unexpected))
        + "\nUse `greeting = _greeting(name)` for the salutation and `_hidden_text(text)` for the "
        "plain-text copy. Extending ALLOWED_SITES needs a written reason next to the entry."
    )
    stale = ALLOWED_SITES - found
    assert not stale, f"Sanctioned sites no longer bypass the helpers — delete them: {sorted(stale)}"


def test_helpers_are_defined_in_the_module():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {GREETING_HELPER, HIDDEN_TEXT_HELPER} <= defined
