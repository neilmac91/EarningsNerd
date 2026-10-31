"""Structural gate: a recipient's name enters an email template ONLY through the greeting helpers.

Seven templates in ``app/services/email_service.py`` once wrote ``f"Hi {name},"`` straight into
HTML, and every sender appended the plain-text copy raw inside ``<pre style="display:none">``.
The name now goes through helpers: ``_greeting`` escapes and single-lines it for the page, and
``_greeting_text`` single-lines it, as typed, for the text part. The plain-text copy is no longer
hidden in the page: it goes to the provider as the mail's text part (E110), since a spam filter
such as rspamd scores 200 hidden characters or more as hidden text. The rendering proof lives in
``test_email_name_escaping.py``. Prose alone would rot (CLAUDE.md rule 12), so this AST walk over
the module pins the shape:

- a recipient's name is read only where the walk lets it, and anywhere else is a finding, whatever the construct around
  it. The walk lets it stand as an argument to a greeting helper (``_greeting(name)``, ``_greeting_text(name)``), as a
  ``name=`` or ``full_name=`` keyword handed to an undecorated function the module defines at its top with that
  parameter (whose body the walk reads the same way), and where it carries none of its text: a test (``if name``,
  ``x if name else y``, a comprehension's ``if``, a case's guard), the operand of a ``not``, and a comparison with
  literals alone (``name == ""``, ``name in ("a", "b")``), each a bool that no code of the module's computes (a
  comparison with anything else hands the name to that operand's ``__eq__`` or ``__contains__``, which the module can
  define). The value of an ``and``, an ``or`` or a conditional expression stands where that expression does. So an
  f-string, ``+``, ``%``, ``.format()``, a store (``parts.append(name)``), a variable (``who = name or "there"``), a key
  a lookup takes (``labels[name]``, which a mapping can hand back), a call of any other function
  (``print(name, file=buffer)``, ``html.escape(name)``, ``"x".translate({88: name})``), a helper of the module's own
  handed it positionally or under another keyword, a collection, a return: each reads it where the walk does not follow,
  and each fails. A name is ``name`` or ``full_name`` written as a variable, an attribute (``user.full_name``) or a
  string (``row["name"]``, ``getattr(user, "full_name")``, ``field = "full_name"``), and a template field that names one
  (``{name}``, ``{0.full_name}``, ``{r[name]}``, a field in another's format spec, ``%(name)s``, ``$name``), which a
  mapping fills without the name written; a dictionary's key (``{"name": sender}``) and ``hasattr``'s attribute (a bool)
  read none. A greeting helper, ``_wrap_text``, ``_preheader`` and each function the walk hands such a keyword to are
  bound once, by their ``def``s: bound again anywhere (a nested ``def``, a second one, an import, an assignment, a
  parameter) or one of the helpers decorated, a call of one may reach other code, and that fails. So does a binding of a
  name the walk trusts as something else: ``getattr``, ``setattr``, ``hasattr`` and ``delattr``, which it trusts as the
  builtins, and ``send_email``, which it trusts as ``from app.services.resend_service import send_email`` binds it. Nor
  does the module store or delete an attribute (an assignment, ``del``, ``setattr()``, ``delattr()``), which can rebind
  a name the walk trusts on the module that binds it (``resend_service.send_email = keep``) or patch an object a helper
  calls (``html.escape = str``). And its top binds each name once (a default, a decorator or a base, which runs there,
  among the ways), shadows no builtin and declares nothing ``global``, so what a helper reads from the module (``html``,
  ``_LINE_SEPARATORS``, ``len``) is what the source binds there: ``html = re`` at the top, or ``global html`` in a
  function, would change what ``_greeting`` escapes with;
- the module imports only what the walk reads, each as written: ``from __future__ import annotations``, ``html``,
  ``re``, ``from app.config import settings`` and ``from app.services.resend_service import send_email``, and reads of
  each only the attributes ``_IMPORTS`` names (``html.escape``, ``re.compile``, ``settings.FRONTEND_URL``), however
  reached, ``getattr()`` among the ways; what each binds is bound by that import alone, anywhere, and read only by such
  an attribute, a call (``send_email(...)``) or ``getattr()``, never handed on whole (``helper(re)``), where its
  attributes would go unread. Any other module, or another attribute of an allowed one (``re.enum.bltns`` is the
  builtins module, ``re.functools`` writes attributes), may run code, reach a frame's locals or an object's referents,
  patch an object by a name, or fill a template in a syntax of its own (``jinja2``, which the backend installs,
  ``string.Formatter``, ``unittest.mock``), so importing or reading it fails; a new import or attribute joins
  ``_IMPORTS`` with what it is for;
- what reaches a value or fills a template without writing a name fails closed: ``locals``, ``vars`` and ``globals``,
  which hand back a scope, however read; the attributes that hand on the values an object, a scope or a closure holds
  (``__dict__``, ``__globals__``, ``__builtins__``, ``__closure__``, ``cell_contents``, ``f_locals``, ``f_globals``,
  ``f_builtins``) and a template field that reads one; ``getattr``, ``setattr``, ``hasattr`` and ``delattr`` handed on
  uncalled, or ``getattr()`` and ``hasattr()`` called by a name not written there or by a dunder's; a template filled
  where the walk cannot read it (``page.format(**row)``, ``page % row``, ``template.substitute(row)``, an f-string,
  whose text its values write: ``f"%({key})s" % row``; a filler handed on uncalled, ``fill = page.format``); an operator
  or a protocol called by its name with anything but literals (``str.__mod__(page, row)``); the builtins that run code
  (``eval``, ``exec``, ``compile``, ``__import__``, ``breakpoint``) and ``__builtins__``, and those, the scope and the
  by-name builtins as another object's attribute (``len.__self__.locals()``, ``obj.eval``, ``obj.setattr``), but for
  ``re.compile``; and a ``Formatter``, which may be string's, whose ``get_field`` reads a value by a dotted path
  (``"0.full_name"``), the modules that reach a frame's locals or an object's referents, run code, or read a value by a
  path (among them ``importlib``, ``builtins``, ``inspect``, ``sys``, ``traceback``, ``gc``, and ``operator`` and its C
  twin), and the template engines (``jinja2``, ``mako``, ``chevron``, ``pystache``, ``django``) and the ``templating``
  modules that wrap one, each reached through another object's attribute (``x.sys``), by ``getattr()``, or named whole
  by a string (``c.__name__ == "Formatter"``). So does a string that writes a name as a step of a path, or anywhere
  after the opener of a template block the walk does not parse (``{{``, ``{%``, ``<%``, ``#{``; a ``str.format``
  template's escaped brace among them, which the module, writing its pages as f-strings, writes nowhere), since an
  engine finds the block's closer by balancing brackets, skipping strings or delimiters the template sets itself
  (``"0.full_name"``, ``"{{ user.full_name }}"``, ``"{{ {1: {2: 3}} and name }}"``, ``"@name"``); a CSS selector that
  names one (``.name``, ``[name]``) reads as such a path, and the module, styling inline, writes none. The module writes
  its pages as f-strings and uses none of them. What the walk cannot see is a name, or a word it refuses, reached by
  reflection that writes none of these whole (``object.__subclasses__()``, ``"Format" + "ter"``), by a key computed at
  run time (``row[key]``, a key a dictionary's literal hands back), or held in a value read whole (an object or a row
  that carries one, where the module takes the name as a string), what a page does with the greeting ``_greeting``
  escaped (``html.unescape(greeting)``), and what a caller does with a text part a function returns
  (``html, text = render_welcome_email(...)``), which no page needs and the rendering proof catches: it renders every
  sender with a markup-shaped name. The greeting helpers' own bodies are exempt;
- every ``greeting = ...`` assignment is a call to ``_greeting``;
- ``_greeting_text``, which keeps the name as typed, is called only inside ``_greeting`` and in a text part: the value
  of a ``text_body = ...`` assignment of that one name, in a function or the module (a class body binds an attribute,
  read where the walk does not follow), which it joins as an f-string's value (not in a format spec, which the formatted
  value's ``__format__`` reads) and by ``+`` beside what the language alone builds a string of (a literal, an f-string,
  a conditional or a concatenation of those, one of those through a method of str's that builds a str of its own:
  ``", ".join(rows)``, ``.strip()``; an f-string only with a literal part, and no ``format``, which return what a
  value's ``__format__`` does, whose methods may be its own), as anything else gets it in its ``__add__`` or
  ``__radd__``: a page that greets with it would print a markup-shaped name as markup. For the same reason ``text_body``
  is read only as ``_wrap_text``'s text (``text_body += x`` reads it, and hands it to ``x``'s ``__radd__``),
  ``_wrap_text`` reads its text, its first positional parameter, only in the string its own body returns, built the same
  way (a read in a function it nests fails, as that function's return goes elsewhere, and so does a ``_wrap_text`` that
  takes no such parameter or is no plain ``def``), and ``_wrap_text()`` stands only where its value leaves as the mail's
  text part: ``send_email``'s ``text=`` keyword, or the last element of a returned tuple;
- the hidden-text literal (``display:none``) appears only inside the module's ``_preheader``, the one helper that hides
  text (the line an inbox lists beside the subject): a helper that hides a copy of the text part, as ``_hidden_text``
  did, or another function named so, fails here. This walk checks where the literal sits, not what the helper escapes:
  that it escapes its line as a unit is held by ``test_mail_rendered_addresses.py``'s escape test, and that no page
  hides other text by any means by its hidden-text check.

The result must equal the allow-list EXACTLY (today: empty). A new template that bypasses a
helper fails with a pointer to the fix; a site that is ever sanctioned must carry a written reason.
"""
import ast
import builtins
import re
import string
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "app" / "services" / "email_service.py"

# (function, offence) pairs allowed to bypass the helpers. Empty: every template uses them.
ALLOWED_SITES: set[tuple[str, str]] = set()

NAME_IDS = {"name", "full_name"}
GREETING_HELPER = "_greeting"
GREETING_TEXT_HELPER = "_greeting_text"
TEXT_PART = "text_body"
TEXT_WRAPPER = "_wrap_text"
TRANSPORT = "send_email"
TRANSPORT_MODULE = "app.services.resend_service"
PREHEADER_HELPER = "_preheader"
HIDDEN_TEXT_HELPERS = frozenset({PREHEADER_HELPER})
HIDDEN_COPY_MARKER = "display:none"


GREETING_HELPERS = frozenset({GREETING_HELPER, GREETING_TEXT_HELPER})
# The methods that fill a template with what they are handed, which the walk reads only where the template is a string
# literal written at the call, its fields read there (an f-string's text is what its values format to, which only a run
# reads).
_FILLING = frozenset({"format", "format_map", "vformat", "substitute", "safe_substitute"})
# What reaches a value without writing its name: the functions that hand back a scope, the attributes that hand on the
# values an object, a scope or a closure holds, the functions that reach an attribute by a name, the builtins that run
# code, the modules that reach a frame's locals or an object's referents, run code or read a value by a path, string's
# Formatter, which reads one by a field's path, and the template engines with the templating modules that wrap one
# (starlette's and fastapi's), whose templates (in a syntax of their own, or in files) the walk does not read: each read
# where an attribute, a getattr() or a string names it, since importing any of them fails (_IMPORTS). The module uses
# none of them.
_SCOPES = frozenset({"locals", "vars", "globals"})
_NAMESPACES = frozenset({
    "__dict__", "__globals__", "__builtins__", "__closure__", "cell_contents", "f_locals", "f_globals", "f_builtins",
})
_BY_NAME = frozenset({"getattr", "setattr", "hasattr", "delattr"})
_STORES_BY_NAME = frozenset({"setattr", "delattr"})
_CODE = frozenset({"eval", "exec", "compile", "__import__", "breakpoint", "__builtins__"})
_REFLECTING = frozenset({"importlib", "builtins", "inspect", "sys", "traceback", "gc", "operator", "_operator"})
_FIELD_READER = "Formatter"
_TEMPLATE_ENGINES = frozenset({"jinja2", "mako", "chevron", "pystache", "django", "templating"})
_REFUSED_WORDS = _SCOPES | _NAMESPACES | _BY_NAME | _CODE | _REFLECTING | _TEMPLATE_ENGINES | {_FIELD_READER}
# The imports the walk reads, each as written, with the attributes the module reads of what each binds: any other module,
# or another attribute of an allowed one (re.enum.bltns is the builtins module, re.functools writes attributes), may run
# code, reach a frame, patch an object or fill a template in a syntax of its own (jinja2, which the backend installs,
# string's Formatter, unittest.mock), so importing or reading it fails. A new import or attribute joins this list with
# what it is for.
_IMPORTS: dict[tuple[str, str | None], frozenset[str]] = {
    ("__future__", "annotations"): frozenset(),  # annotations kept as strings
    ("html", None): frozenset({"escape", "unescape"}),  # the escaping _greeting applies, and a link's address unescaped
    ("re", None): frozenset({"compile", "IGNORECASE", "DOTALL", "Match", "Pattern"}),  # patterns, and their types
    ("app.config", "settings"): frozenset({"FRONTEND_URL"}),  # the frontend's address
    # A readiness boolean only: no recipient data, template access or other module attributes.
    ("app.services", "legal_readiness_service"): frozenset({"is_marketing_available"}),
    (TRANSPORT_MODULE, TRANSPORT): frozenset(),  # the transport, to which a mail's text part goes: only called
}
# What each allowed import binds, and the attributes the module may read of it.
_IMPORTED_ATTRIBUTES = {name or module: attributes for (module, name), attributes in _IMPORTS.items()}
# The builtins a module's top could shadow for a helper that reads them (len and max, which _preheader reads).
_BUILTINS = frozenset(name for name in dir(builtins) if not name.startswith("_"))
_UNREAD_MODULE = "which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"
# A name written as a step of a path ("0.full_name", "row[name]", "@name"); $name is a field the walk reads.
_PATH_STEP = re.compile(r"""(?:[.\[]\s*["']?|@\s*)(name|full_name)\b""")
# The openers of the template blocks the walk does not parse ("{{ name }}", "{% if name %}", "<%= name %>", "#{name}"):
# an engine reads its block to a closer it finds by balancing brackets, skipping strings or delimiters the template sets
# itself ("{{ {1: {2: 3}} and name }}", "{{=| |=}} |name|"), so a name anywhere after one reads as in the block.
_BLOCK_OPENERS = ("{{", "{%", "<%", "#{")
_NAME_WORD = re.compile(r"\b(name|full_name)\b")
# The methods of a str that build a str of their own from it, whatever they are handed: format and format_map return
# what a value's __format__ does, maketrans a mapping of what it was handed, and the rest no str.
_STR_METHODS = frozenset({
    "capitalize", "casefold", "center", "expandtabs", "join", "ljust", "lower", "lstrip", "removeprefix", "removesuffix",
    "replace", "rjust", "rstrip", "strip", "swapcase", "title", "translate", "upper", "zfill",
})
# A method named as Python names an operator or a protocol (str.__mod__, "<p>Hi ".__add__).
_DUNDER = re.compile(r"__\w+__")
# A %-template's key and a $-template's placeholder, beside str.format's fields.
_PERCENT_KEY = re.compile(r"%(?:%|\(([^)]*)\))")


def _field_names(template: str) -> set[str]:
    """Each name a template's fields read: each word of a str.format field's chain (``{0.full_name}``, ``{r[name]}``),
    a field in a format spec among them (``{0:{1.full_name}^9}``), a ``%(key)s`` key, and a ``$key`` or ``${key}``
    placeholder."""
    found: set[str] = set()
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError:
        parsed = []  # no str.format template; its other placeholders still count
    for _literal, field, spec, _conversion in parsed:
        found.update(re.findall(r"[A-Za-z_]\w*", field or ""))
        found |= _field_names(spec) if spec else set()
    found.update(key for key in _PERCENT_KEY.findall(template) if key)
    found.update(match.group("named") or match.group("braced") or "" for match in string.Template.pattern.finditer(template))
    return found


def _block_names(text: str) -> set[str]:
    """Each name a string writes after the first opener of a template block: where the block ends is the engine's
    reading, which no reading short of its own lexer follows, so the walk reads the rest of the string as the block."""
    inside = min((text.index(opener) + len(opener) for opener in _BLOCK_OPENERS if opener in text), default=None)
    return set() if inside is None else set(_NAME_WORD.findall(text, inside))


def _literal_string(node: ast.expr) -> bool:
    """Whether an expression is a string literal, whose text, a template's fields among it, the walk reads where it
    stands (an f-string's is what its values format to, which only a run reads)."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _str_typed(node: ast.expr) -> bool:
    """Whether an expression is a string the language alone builds, a str and no subclass of one: a literal, an f-string
    with a literal part (one of a field alone is what its value's __format__ returns, whose methods may be its own), a
    conditional or a concatenation of those, or one of those through a method of str's that builds a str of its own
    (``", ".join(rows)``; not ``"".maketrans(table).get(97)``, which hands back what the table holds), none of which
    hands a string beside it to code of the module's."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _str_typed(node.left) and _str_typed(node.right)
    if isinstance(node, ast.IfExp):
        return _str_typed(node.body) and _str_typed(node.orelse)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return _str_typed(node.func.value) and node.func.attr in _STR_METHODS
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(part, ast.Constant) for part in node.values)
    return _literal_string(node)


def _imported_as(alias: ast.alias) -> str:
    """How a finding names what an import binds."""
    return f"{alias.name} as {alias.asname}" if alias.asname else alias.name


def _literal(node: ast.AST) -> bool:
    """Whether an expression is a literal, or a tuple, a list or a set of literals: what a comparison with a name computes
    by the name's own type, with no code of the module's."""
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(isinstance(element, ast.Constant) for element in node.elts)
    return isinstance(node, ast.Constant)


def _callee(call: ast.Call) -> str:
    """The name a call calls a function or a method by, or what it calls."""
    return call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", type(call.func).__name__)


def _described(call: ast.Call) -> str:
    """How a finding names what a call calls: ``print()``, ``append()``, or what a call returns."""
    return f"{_callee(call)}()" if isinstance(call.func, (ast.Name, ast.Attribute)) else "what a call returns"


def _bound(node: ast.AST) -> str | None:
    """The name a node binds, if any: a store or a delete, a parameter, an import, a def or a class, an except's or a
    pattern's capture."""
    if isinstance(node, ast.Name):
        return None if isinstance(node.ctx, ast.Load) else node.id
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, ast.alias):
        return node.asname or node.name.split(".")[0]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        return node.name
    if isinstance(node, ast.MatchMapping):
        return node.rest
    return None


def _binds(node: ast.AST, first: set[int]) -> str | None:
    """The name a node binds, beside the first def or class of each name at the module's top (``first``)."""
    return None if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and id(node) in first else _bound(node)


class _Finder(ast.NodeVisitor):
    """Collect (enclosing function, offence) for every place a recipient's name is read outside the places the walk
    lets it stand, and every way it cannot follow."""

    def __init__(self, tree: ast.Module) -> None:
        self.hits: list[tuple[str, str]] = []
        self._stack: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef] = []
        self._parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        self._called = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self._docstrings = {
            id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
        }
        first: dict[str, int] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                first.setdefault(node.name, id(node))
        self._first = set(first.values())
        # Each binding at the module's top after the first of its name, and each of a builtin's name there.
        seen: set[str] = set()
        self._rebound_at_top: set[int] = set()
        self._shadowing: set[int] = set()
        bindings = [node for node in ast.walk(tree) if _bound(node) and self._at_top(node)]
        for node in sorted(bindings, key=lambda node: (node.lineno, node.col_offset)):
            name = _bound(node)
            if name in seen:
                self._rebound_at_top.add(id(node))
            seen.add(name)
            if name in _BUILTINS:
                self._shadowing.add(id(node))
        # The parameters a keyword reaches in each undecorated function the module's top defines first, and the
        # functions the walk follows a name into, which must not be bound again.
        self._keywords = {
            node.name: {argument.arg for argument in (*node.args.args, *node.args.kwonlyargs)}
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) in self._first and not node.decorator_list
        }
        self._held = GREETING_HELPERS | {TEXT_WRAPPER, PREHEADER_HELPER}
        self._followed = self._held | {function for function, keywords in self._keywords.items() if keywords & NAME_IDS}
        # The parameter _wrap_text takes its text by: the first positional one of the plain def the module's top first
        # binds it to.
        wrapper = next(
            (node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == TEXT_WRAPPER
             and id(node) in self._first),
            None,
        )
        positional = [*wrapper.args.posonlyargs, *wrapper.args.args] if isinstance(wrapper, ast.FunctionDef) else []
        self._wrapped_text = positional[0].arg if positional else None

    def _at_top(self, node: ast.AST) -> bool:
        """Whether a binding binds its name at the module's top: no function, lambda or class holds it, nor a
        comprehension, unless an assignment expression binds it, which binds past one. What runs in the scope around a
        function or a class does not stand in it: a default, an annotation, a decorator, a base, a class keyword."""
        child, holder = node, self._parents.get(node)
        walrus = isinstance(holder, ast.NamedExpr) and holder.target is node
        around = False  # whether the climb runs in the scope around the next function it reaches
        while holder is not None:
            if isinstance(holder, ast.arguments) and (child in holder.defaults or child in holder.kw_defaults):
                around = True
            elif isinstance(holder, ast.arg) and child is holder.annotation:
                around = True
            elif isinstance(holder, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if not (around or child in getattr(holder, "decorator_list", ()) or child is getattr(holder, "returns", None)):
                    return False
                around = False
            elif isinstance(holder, ast.ClassDef) and child in holder.body:
                return False
            elif isinstance(holder, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) and not walrus:
                return False
            child, holder = holder, self._parents.get(holder)
        return True

    def _where(self) -> str:
        return self._stack[-1].name if self._stack else "<module>"

    def _in(self, *helpers: str) -> bool:
        """Whether the walk is in the body of one of these helpers, as the module's top first defines it."""
        return len(self._stack) == 1 and self._stack[0].name in helpers and id(self._stack[0]) in self._first

    def _within(self, helper: str) -> bool:
        """Whether the walk is anywhere in a helper, as the module's top first defines it: its body or what it nests."""
        return bool(self._stack) and self._stack[0].name == helper and id(self._stack[0]) in self._first

    def _hit(self, offence: str) -> None:
        self.hits.append((self._where(), offence))

    def visit(self, node: ast.AST) -> None:
        name = _bound(node)
        if name in _BY_NAME:
            self._hit(f"binds {name}, which the walk trusts as the builtin")
        elif name == TRANSPORT and not self._imported(node):
            self._hit(f"binds {TRANSPORT} otherwise than from {TRANSPORT_MODULE}, the import the walk trusts")
        elif (bound := _binds(node, self._first)) in self._followed:
            self._hit(f"binds {bound} again, so a call of it may reach other code than the function the walk reads")
        elif name in _IMPORTED_ATTRIBUTES and not self._allowed_import(node):
            self._hit(f"binds {name}, which an allowed import binds: the walk reads the name only as that import")
        elif id(node) in self._rebound_at_top:
            self._hit(f"binds {name} again at the module's top, so a helper that reads it may read another value")
        elif id(node) in self._shadowing:
            self._hit(f"binds {name}, a builtin's name, at the module's top, so a helper that reads the builtin may read another value")
        super().visit(node)

    def _allowed_import(self, node: ast.AST) -> bool:
        """Whether a node binds a name as an allowed import does: import <module> or from <module> import <name>."""
        parent = self._parents.get(node)
        if not isinstance(node, ast.alias) or node.asname:
            return False
        if isinstance(parent, ast.Import):
            return (node.name, None) in _IMPORTS
        return isinstance(parent, ast.ImportFrom) and not parent.level and (parent.module, node.name) in _IMPORTS

    def visit_Global(self, node: ast.Global) -> None:
        self._hit(f"declares {', '.join(node.names)} global, so a function may rebind a name the module's helpers read")
        self.generic_visit(node)

    def _imported(self, node: ast.AST) -> bool:
        """Whether a node binds the transport as the walk trusts it: from app.services.resend_service import send_email."""
        parent = self._parents.get(node)
        return (
            isinstance(node, ast.alias) and node.name == TRANSPORT and isinstance(parent, ast.ImportFrom)
            and parent.module == TRANSPORT_MODULE
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name in self._held and id(node) in self._first and node.decorator_list:
            self._hit(f"decorates {node.name}, so a call of it may reach other code than the helper's body")
        if node.name == TEXT_WRAPPER and id(node) in self._first and self._wrapped_text is None:
            self._hit(f"{TEXT_WRAPPER} takes its text by no positional parameter of a plain def, so the walk cannot hold it")
        self._stack.append(node)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]
    visit_ClassDef = visit_FunctionDef  # type: ignore[assignment]

    def _stands(self, node: ast.AST) -> tuple[ast.AST, ast.AST | None]:
        """The expression a read decides, past any ``and``, ``or`` or conditional expression whose value it may be,
        and what holds that expression."""
        parent = self._parents.get(node)
        while isinstance(parent, ast.BoolOp) or isinstance(parent, ast.IfExp) and node is not parent.test:
            node, parent = parent, self._parents.get(parent)
        return node, parent

    def _sanctioned(self, read: ast.AST) -> bool:
        """Whether a read of a name stands where the walk lets it: a greeting helper's argument, a name= keyword to an
        undecorated function the module defines with that parameter, or where it carries none of its text."""
        node, parent = self._stands(read)
        if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not):
            return True  # a bool carries none of its text
        if isinstance(parent, ast.Compare):
            return all(_literal(operand) for operand in (parent.left, *parent.comparators) if operand is not node)
        if isinstance(parent, (ast.If, ast.While, ast.Assert, ast.IfExp)) and node is parent.test:
            return True
        if isinstance(parent, ast.match_case) and node is parent.guard:
            return True
        if isinstance(parent, ast.comprehension) and node in parent.ifs:
            return True
        if isinstance(parent, ast.Call) and node in parent.args:
            return isinstance(parent.func, ast.Name) and parent.func.id in GREETING_HELPERS
        if isinstance(parent, ast.keyword) and parent.arg in NAME_IDS:
            call = self._parents[parent]  # a call's, or a class's
            return (
                isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and parent.arg in self._keywords.get(call.func.id, set())
            )
        return False

    def _context(self, read: ast.AST) -> str:
        """Where a read stands, for its finding."""
        node, parent = self._stands(read)
        if isinstance(parent, ast.FormattedValue):
            return "in an f-string"
        if isinstance(parent, ast.Call):
            return "as what a call calls" if node is parent.func else f"as an argument to {_described(parent)}"
        if isinstance(parent, ast.keyword):
            call = self._parents[parent]
            return f"as {parent.arg or '**'}= to {_described(call) if isinstance(call, ast.Call) else 'a class'}"
        if isinstance(parent, ast.Attribute):
            return f"as .{parent.attr}'s receiver"
        if isinstance(parent, ast.Subscript):
            return "as a key a lookup takes, which a mapping can hand back" if node is parent.slice else "as what a lookup reads"
        if isinstance(parent, ast.BinOp):
            return "in an operation"
        if isinstance(parent, ast.Compare):
            return "in a comparison with what is no literal, whose __eq__ or __contains__ the module can define"
        if isinstance(parent, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            return "into a variable"
        if isinstance(parent, (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.Starred)):
            return "into a collection"
        if isinstance(parent, ast.arguments):
            return "as a default"
        kind = type(parent).__name__.lower()
        return f"in {'an' if kind[0] in 'aeiou' else 'a'} {kind}"

    def _read(self, read: ast.AST, written: str) -> None:
        if not self._in(*GREETING_HELPERS) and not self._sanctioned(read):
            self._hit(f"{written} read {self._context(read)}, outside the greeting helpers")

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in NAME_IDS:
            self._read(node, node.id)
        elif node.id in _CODE:
            self._hit(f"{node.id} runs code the walk does not read")
        elif node.id in _SCOPES:
            self._hit(f"{node.id} hands back a scope whole, which the walk does not follow")
        elif node.id in _BY_NAME and id(node) not in self._called:
            self._hit(f"{node.id} handed on uncalled, which reaches an attribute by a name the walk does not read")
        elif node.id == _FIELD_READER:
            self._hit(f"{_FIELD_READER} may be string's, which reads a value by a field's path the walk does not read")
        elif node.id in _IMPORTED_ATTRIBUTES and isinstance(node.ctx, ast.Load) and not self._read_by_attribute(node):
            self._hit(f"{node.id} read whole, so its attributes are read where the walk does not read them (_IMPORTS)")
        elif node.id == TEXT_PART and isinstance(node.ctx, ast.Load) and not self._wrapped(node):
            self._hit(f"{TEXT_PART} read but as {TEXT_WRAPPER}()'s text, though it holds the name as typed")
        elif node.id == self._wrapped_text and self._within(TEXT_WRAPPER) and isinstance(node.ctx, ast.Load) and not (
            self._in(TEXT_WRAPPER) and self._kept(node)
        ):
            self._hit(f"{TEXT_WRAPPER} reads its text elsewhere than in the string it returns")

    def _read_by_attribute(self, node: ast.Name) -> bool:
        """Whether an allowed import's name stands where the walk reads what it reaches: an attribute's receiver, what a
        call calls, or getattr()'s object."""
        parent = self._parents.get(node)
        return (
            isinstance(parent, ast.Attribute) and parent.value is node
            or isinstance(parent, ast.Call) and (
                parent.func is node
                or isinstance(parent.func, ast.Name) and parent.func.id == "getattr" and parent.args[:1] == [node]
            )
        )

    def _wrapped(self, node: ast.Name) -> bool:
        """Whether text_body stands as _wrap_text's text."""
        call = self._parents.get(node)
        return isinstance(call, ast.Call) and _callee(call) == TEXT_WRAPPER and bool(call.args) and call.args[0] is node

    def _leaves(self, call: ast.Call) -> bool:
        """Whether _wrap_text's value leaves as the mail's text part: send_email's text= keyword, or the last element of
        a returned tuple."""
        parent = self._parents.get(call)
        if isinstance(parent, ast.keyword):
            sent = self._parents.get(parent)
            return parent.arg == "text" and isinstance(sent, ast.Call) and isinstance(sent.func, ast.Name) and sent.func.id == TRANSPORT
        return isinstance(parent, ast.Tuple) and parent.elts[-1] is call and isinstance(self._parents.get(parent), ast.Return)

    def _built(self, node: ast.AST) -> tuple[ast.AST, ast.AST | None]:
        """What an expression is built into, past each f-string it stands in as a value (not in a format spec, which the
        formatted value's __format__ reads) and each concatenation beside a string the language alone builds (anything
        else gets it in its __add__ or __radd__), and what holds that."""
        parent = self._parents.get(node)
        while (
            isinstance(parent, ast.JoinedStr)
            or isinstance(parent, ast.FormattedValue) and node is parent.value
            or isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add)
            and _str_typed(parent.right if node is parent.left else parent.left)
        ):
            node, parent = parent, self._parents.get(parent)
        return node, parent

    def _kept(self, node: ast.Name) -> bool:
        """Whether _wrap_text's text stands only in the string it returns, built as a text part is (read in its own body,
        not a function it nests, whose return goes elsewhere)."""
        built, parent = self._built(node)
        return isinstance(parent, ast.Return) and parent.value is built

    def _in_text_part(self, call: ast.Call) -> bool:
        """Whether a call stands in a text part: built as an f-string's value or beside strings the language alone builds
        into the value of a text_body = ... assignment of that one name, in a function or the module (in a class body it
        binds an attribute, read where the walk does not follow)."""
        built, parent = self._built(call)
        return (
            not (self._stack and isinstance(self._stack[-1], ast.ClassDef))
            and isinstance(parent, ast.Assign) and parent.value is built and len(parent.targets) == 1
            and isinstance(parent.targets[0], ast.Name) and parent.targets[0].id == TEXT_PART
        )

    def _in_text_part_assignment(self, node: ast.AST) -> bool:
        """Whether a node stands anywhere in the value of a text_body = ... assignment of that one name, outside a class
        body."""
        statement = self._parents.get(node)
        while statement is not None and not isinstance(statement, ast.stmt):
            statement = self._parents.get(statement)
        return (
            not (self._stack and isinstance(self._stack[-1], ast.ClassDef))
            and isinstance(statement, ast.Assign) and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == TEXT_PART
        )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if not isinstance(node.ctx, ast.Load):
            self._hit(
                f"{'deletes' if isinstance(node.ctx, ast.Del) else 'stores'} .{node.attr}, which may rebind a name the walk "
                "trusts or patch an object a helper calls"
            )
        owner = node.value.id if isinstance(node.value, ast.Name) and node.value.id in _IMPORTED_ATTRIBUTES else None
        if node.attr in NAME_IDS and isinstance(node.ctx, ast.Load):
            self._read(node, f".{node.attr}")
        elif owner and isinstance(node.ctx, ast.Load) and node.attr not in _IMPORTED_ATTRIBUTES[owner]:
            self._hit(f"reads {owner}.{node.attr}, an attribute of an allowed import the walk does not read (_IMPORTS)")
        elif node.attr in _NAMESPACES:
            self._hit(
                f".{node.attr} hands on the values an object, a scope or a closure holds, a name among them, which the "
                "walk does not follow"
            )
        elif node.attr in _REFLECTING:
            self._hit(f".{node.attr} reaches the {node.attr} module through another name, which the walk does not follow")
        elif node.attr == _FIELD_READER:
            self._hit(f".{_FIELD_READER} may be string's, which reads a value by a field's path the walk does not read")
        elif node.attr in _TEMPLATE_ENGINES:
            self._hit(f".{node.attr} reaches a template engine through another name, whose templates the walk does not read")
        elif node.attr in _SCOPES | _CODE | _BY_NAME and not owner:
            self._hit(
                f".{node.attr} may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, "
                "through another object"
            )
        elif node.attr in _FILLING and id(node) not in self._called:
            self._hit(f".{node.attr} handed on uncalled, a template's filler the walk does not follow")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and id(node) not in self._docstrings:
            parent = self._parents.get(node)
            keyed = isinstance(parent, ast.Dict) and any(key is node for key in parent.keys)  # a key written, not read
            asked = (  # hasattr answers a bool
                isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id == "hasattr"
                and node in parent.args[1:]
            )
            if node.value in NAME_IDS and not keyed and not asked:
                read: ast.AST = node
                if isinstance(parent, ast.Subscript) and parent.slice is node:
                    read = parent  # row["name"] reads the name
                elif isinstance(parent, ast.keyword) or isinstance(parent, ast.Call) and node in parent.args:
                    read = parent if isinstance(parent, ast.Call) else self._parents[parent]  # getattr(user, "full_name")
                self._read(read, repr(node.value))
            fields = _field_names(node.value) & (NAME_IDS | _NAMESPACES)
            for field in sorted(fields):
                if field in NAME_IDS:
                    self._hit(f"a template field reads {field}, which a mapping fills without the name written")
                else:
                    self._hit(f"a template field reads {field}, which hands on the values an object, a scope or a closure holds")
            for step in sorted(({match.group(1) for match in _PATH_STEP.finditer(node.value)} | _block_names(node.value)) - fields):
                self._hit(f"a string reads {step} by a path or after a template block's opener, which the walk does not parse")
            by_name = isinstance(parent, ast.Call) and _callee(parent) in _BY_NAME and node in parent.args[1:2]
            if node.value in _REFUSED_WORDS and not by_name:
                self._hit(f"a string names {node.value}, which reaches what the walk does not follow")
        if isinstance(node.value, str) and HIDDEN_COPY_MARKER in node.value and not self._in(*HIDDEN_TEXT_HELPERS):
            self._hit(f"hidden text built outside the module's {PREHEADER_HELPER}()")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if (alias.name, None) not in _IMPORTS:
                self._hit(f"imports {_imported_as(alias)}, {_UNREAD_MODULE}")
            elif alias.asname:
                self._hit(f"imports {alias.name} as {alias.asname}: the walk reads an allowed import only as written")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            if (module, alias.name) not in _IMPORTS:
                self._hit(f"imports {_imported_as(alias)} from {module}, {_UNREAD_MODULE}")
            elif alias.asname:
                self._hit(f"imports {alias.name} as {alias.asname} from {module}: the walk reads an allowed import only as written")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Mod) and not _literal_string(node.left) and not isinstance(node.right, ast.Constant):
            self._hit("% fills a template the walk cannot read, or takes a modulo by what it does not read")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.op, ast.Mod) and not isinstance(node.value, ast.Constant):
            self._hit("%= fills a template the walk cannot read, or takes a modulo by what it does not read")
        target = node.target
        if isinstance(target, ast.Name) and (
            target.id == TEXT_PART or target.id == self._wrapped_text and self._within(TEXT_WRAPPER)
        ):
            self._hit(f"{target.id} augmented, which reads the text and hands it to the other operand's code")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        literal = all(isinstance(value, ast.Constant) for value in arguments)
        called = _callee(node)
        if isinstance(node.func, ast.Name) and called in _BY_NAME:
            reached = node.args[1] if len(node.args) > 1 else None
            if called in _STORES_BY_NAME:
                self._hit(
                    f"{called}() {'deletes' if called == 'delattr' else 'stores'} an attribute, which may rebind a name the "
                    "walk trusts or patch an object a helper calls"
                )
            elif not (isinstance(reached, ast.Constant) and isinstance(reached.value, str) and not _DUNDER.fullmatch(reached.value)):
                self._hit(f"{called}() reaches an attribute by a name the walk does not read")
            elif called == "getattr" and isinstance(node.args[0], ast.Name) and node.args[0].id in _IMPORTED_ATTRIBUTES:
                if reached.value not in _IMPORTED_ATTRIBUTES[node.args[0].id]:
                    self._hit(
                        f"getattr() reads {node.args[0].id}.{reached.value}, an attribute of an allowed import the walk "
                        "does not read (_IMPORTS)"
                    )
            elif reached.value in _REFUSED_WORDS | _FILLING:
                self._hit(f"{called}() reaches {reached.value}, which the walk does not follow")
        if isinstance(node.func, ast.Attribute):
            if _DUNDER.fullmatch(called) and not literal:
                self._hit(f".{called}() calls an operator or a protocol by name, which the walk does not read")
            if called in _FILLING and not _literal_string(node.func.value) and not literal:
                self._hit(f".{called}() fills a template the walk cannot read")
        if called == GREETING_TEXT_HELPER and not self._in(GREETING_HELPER) and not self._in_text_part(node):
            if self._in_text_part_assignment(node):
                self._hit(
                    f"{GREETING_TEXT_HELPER}() stands in its text part where its text may go elsewhere than the string: a "
                    "format spec, a binding, or beside what the language does not build alone"
                )
            else:
                self._hit(f"{GREETING_TEXT_HELPER}() outside a text part ({TEXT_PART} = ...)")
        if called == TEXT_WRAPPER and not self._leaves(node):
            self._hit(f"{TEXT_WRAPPER}() stands where its value is no text part ({TRANSPORT}'s text=, a returned tuple's last element)")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(isinstance(target, ast.Name) and target.id == "greeting" for target in node.targets):
            value = node.value
            if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == GREETING_HELPER):
                self._hit(f"greeting built without {GREETING_HELPER}()")
        self.generic_visit(node)


def _raw_name_sites(source: str) -> list[tuple[str, str]]:
    tree = ast.parse(source)
    finder = _Finder(tree)
    finder.visit(tree)
    return finder.hits


# A gate that cannot fail proves nothing: pin what the finder catches and what it lets through.
_FINDER_PROBE = '''
from __future__ import annotations
import contextlib
import functools
import html
import io
import operator
import re
import string
from collections import deque
from functools import partial, wraps
from string import Template
import functools as ft
import string as st
from contextlib import *
import builtins
import _operator
from _functools import reduce
from builtins import eval as run
from os import sys as system

def _greeting_text(name):
    return f"Hi {' '.join(name.split())}," if name else "Hi there,"

def _greeting(name):
    def inner():
        return f"<p>{name}</p>"
    return html.escape(_greeting_text(name))

def _hidden_text(text):
    return f'<pre style="display:none">{html.escape(text)}</pre>'

def _preheader(text):
    return f'<div style="display:none;mso-hide:all;">{html.escape(text)}</div>'

def _wrap_text(text, footer=""):
    return f"{text}\\n\\n{footer}"

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

def raw_preheader(text):
    return f'<div style="display:none;mso-hide:all;">{text}</div>'

def page_greets_as_typed(name):
    greeting = _greeting(name)
    return f"<p>{_greeting_text(name)}</p>"

async def uses_helpers(name, text):
    greeting = _greeting(name)
    text_body = f"{_greeting_text(name)}\\n\\n{text}"
    send_email(text=_wrap_text(text_body))
    return f"{_preheader(text)}<p>{greeting}</p>", _wrap_text(text_body)

def wrapped_name(full_name):
    return f"<p>Hi {str(full_name)},</p>"

def user_object(user):
    return f"<p>Hi {user.full_name},</p>"

def joined(name):
    return "".join(["Hi ", name, ","])

def concatenated_call(name):
    return "Hi " + name.title() + ","

def other_names_are_fine(company_name, ticker, user):
    return f"{company_name} ({ticker}) {user.email}" + ticker + ", ".join([company_name])

def assigned_name(name):
    who = name or "there"
    return f"<p>Hi {who},</p>"

def assigned_chain(user):
    first = user.full_name
    shown, rest = first.strip(), None
    return "<p>Hi " + shown + "</p>"

def looped_name(name):
    return "".join(f"<b>{part}</b>" for part in name.split())

def stored_name(name):
    parts = {}
    parts["who"] = name
    return "<p>Hi {who}</p>".format(**parts)

def assigned_helper(name, company_name):
    greeting = _greeting(name)
    line = greeting
    title = company_name.title()
    return f"<p>{line} {title}</p>"

def keyed_lookup(name, flagged):
    label = {"quality": "partial snapshots"}[name]
    shown = "flagged" if name == "quality" else "clean"
    return f"<p>{label}: {shown} {flagged}</p>"

def augmented(name):
    page = "<p>Hi "
    page += name
    return page

def augmented_onto(user):
    line = user.full_name.strip()
    line += ","
    return line

def percent_augmented(name):
    line = "<p>Hi %s</p>"
    line %= name
    return line

def appended(name):
    parts = ["<p>Hi "]
    parts.append(name)
    return "".join(parts)

def extended(user):
    parts = []
    parts.extend([user.full_name])
    return " ".join(parts)

def inserted(name):
    parts = ["</p>"]
    parts.insert(0, name)
    return "".join(parts)

def updated(name):
    fields = {}
    fields.update(who=name)
    return "<p>Hi {who}</p>".format(**fields)

def defaulted(name):
    fields = {}
    fields.setdefault("who", name)
    return "<p>Hi {who}</p>".format_map(fields)

def added(name):
    seen = set()
    seen.add(name)
    return ", ".join(seen)

def mapped(name):
    return "<p>Hi {who}</p>".format_map({"who": name})

def replaced(name):
    return "<p>Hi NAME</p>".replace("NAME", name)

def looked_up(user):
    return f"<p>Hi {getattr(user, 'full_name')}</p>"

def stores_without_a_name(company_name, families):
    rows = []
    for family_name, family in families.items():
        rows.append(family_name.replace("_", " "))
    rows.append(company_name)
    page = "<p>"
    page += company_name
    return "".join(rows) + page

def template_attribute(user):
    return "<p>Hi {0.full_name}</p>".format(user)

def template_keyword_attribute(user):
    return "<p>Hi {u.name}</p>".format(u=user)

def template_key(row):
    return "<p>Hi {r[name]}</p>".format(r=row)

def template_mapping(row):
    return "<p>Hi {name}</p>".format_map(row)

def template_unpacked(row):
    return "<p>Hi {full_name}</p>".format(**row)

def template_substituted(row):
    return Template("<p>Hi $name</p>").substitute(row) + Template("<p>${full_name}</p>}").substitute(row)

def percent_mapping(row):
    return "<p>Hi %(name)s</p>" % row

def local_names(name):
    return "<p>Hi %(name)s</p>" % locals()

def object_names(user):
    return "<p>Hi {full_name}</p>".format_map(vars(user))

def keyed_name(row):
    return f"<p>Hi {row['name']}</p>"

def fetched_name(row):
    return f"<p>Hi {row.get('full_name')}</p>"

def substituted(name):
    return Template("<p>Hi $who</p>").substitute(who=name)

def resubbed(name, page):
    return re.sub("NAME", name, page)

def appended_left(name):
    parts = deque(["</p>"])
    parts.appendleft(name)
    return "".join(parts)

def written(name):
    buffer = io.StringIO()
    buffer.write(name)
    return f"<p>{buffer.getvalue()}</p>"

def set_attribute(name, holder):
    setattr(holder, "who", name)
    return f"<p>{holder.who}</p>"

def set_item(name):
    fields = {}
    fields.__setitem__("who", name)
    return "<p>Hi {who}</p>".format(**fields)

def fields_without_a_name(user, row, company_name):
    return "<p>{0.email} {r[email]}</p>".format(user, r=row) + "<p>{company}</p>".format(company=company_name)

def a_field_named_so(company_name):
    return "<p>{name}</p>".format(name=company_name)

def keys_without_a_name(row):
    return f"<p>{row['email']} {row.get('ticker')}</p>" + "<p>%(email)s</p>" % row + "<p>%(ticker)s</p>" % {"ticker": row["ticker"]}

_PAGE = "<p>Hi {u.full_name}</p>"

def auto_numbered(user, row):
    return "<p>Hi {.full_name}</p>".format(user) + "<p>Hi {[name]}</p>".format(row)

def held_template(user, row):
    page = "<p>Hi {0.full_name}</p>"
    return [page.format(user), _PAGE.format(u=user), page.format_map(row)]

def held_percent(row):
    page = "<p>Hi %(name)s</p>"
    first = page % row
    page %= row
    return first + page + "<p>{ %(name)s</p>" % row

def held_substitute(row, text):
    template = Template("<p>Hi $name</p>")
    return [template.substitute(row), Template(text).safe_substitute(row)]

def default_read(row):
    return f"<p>Hi {row.setdefault('name', '')}</p>"

def function_stores(name, holder, buffer):
    fields = {}
    operator.setitem(fields, "who", name)
    object.__setattr__(holder, "who", name)
    print(name, file=buffer)
    return ["<p>Hi {who}</p>".format(**fields), f"<p>{holder.who}</p>", f"<p>{buffer.getvalue()}</p>"]

def unread_look_alikes(page, count, row):
    """Each greets no {name}, nor a %(name)s or a $name: a docstring is no template."""
    return [page.format(), page.format("x", 2), "100%%(name)s" % row, str(count % 2), "<p>%s: %s</p>" % (count, count),
            f"<p>{{x}} {count}</p>".format(x=1)]

def bytes_template(row):
    return b"<p>%(full_name)s</p>" % row

def fstring_templates(row, key, user):
    return [f"<p>{{{key}}}</p>".format(**row), f"<p>{{{key}}}</p>".format_map(row), f"<p>%({key})s</p>" % row,
            f"<p>{{0.{key}}}</p>".format(user), f"<p>{key}: %s</p>" % (key,)]

def operators_by_name(name, row, page):
    return ["<p>Hi ".__add__(name), page.__mod__(row), "<p>Hi %(name)s</p>".__mod__(row), str.__mod__(page, row)]

def unbound_stores(name, fields, seen):
    parts = []
    list.append(parts, name)
    dict.update(fields, who=name)
    set.add(seen, name)
    return ["".join(parts), "{who}".format(**fields), "".join(seen)]

def held_by_dict(user, row):
    return f"<p>{user.__dict__}</p>" + "<p>{0.__dict__}</p>".format(user) + f"<p>{row.__getitem__('name')}</p>"

def nested_spec(user):
    return "<p>{0:{1.full_name}^9}</p>".format("x", user)

def reached_by_name(user, field, holder):
    return [getattr(user, field), getattr("<p>Hi ", "__add__"), hasattr(user, field), delattr(holder, field)]

def unread_routes(name, buffer):
    with contextlib.redirect_stdout(buffer):
        print(name)
    return [
        functools.reduce(operator.add, ["<p>Hi ", name]), string.Formatter().vformat("{0}", (name,), {}),
        eval("name"), f"<p>{globals()}</p>",
    ]

def aliased_routes(name):
    held = functools
    return [ft.reduce(str.__add__, ["<p>Hi ", name]), st.Formatter(), held.partial(str.__add__, "<p>Hi ")(name),
            __import__("sys").modules["functools"], sys.modules]

def routed_look_alikes(count, parts, user):
    print("sent")
    list.append(parts, "x")
    return [str(count.__index__()), getattr(user, "email"), functools.wraps, "".join(parts)]

def reflected_routes(name):
    return [
        functools.__dict__["reduce"](str.__add__, ["<p>Hi ", name]), functools.__getattribute__("reduce"),
        sys.__dict__["modules"], builtins.eval("name"), __builtins__["eval"], _operator.add,
        re.functools.reduce(str.__add__, ["<p>Hi ", name]), os.sys.modules, getattr(re, "functools"),
        vars(re)["functools"], re.__dict__.get("functools"),
    ]

def held_methods(name, parts, row, page):
    fill = "<p>Hi {}</p>".format
    put = parts.append
    get = row.get
    return [fill(name), put(name), get("name"), list(map(page.format, [name]))]

def shadowing(string):
    return len(string)

def held_look_alikes(page, parts, row):
    parts.append("x")
    return ["<p>{}</p>".format(page), row.get("email"), re.compile("x").sub("y", page), functools.wraps, row["email"]]

def render(name, user=None):
    greeting = _greeting(name)
    return f"<p>{greeting}</p>"

def positional_only(name, /, **rest):
    return _greeting(name)

def card(who):
    return f"<p>{who}</p>"

def keyword_only(*, name):
    return _greeting(name)

def handed_on(name, user):
    return [render(name=name), render(name, user), render(who=name), send_email(name=name), _greeting(name=name),
            _greeting(user.full_name or "there"), positional_only("x", name=name), card(who=name), keyword_only(name=name),
            user._greeting(name)]

def tested(name, row, labels):
    if name:
        pass
    while name:
        break
    assert name, name
    shown = "flagged" if name else "clean"
    known = name in labels and not name
    return [shown, known, labels[name], labels[row["name"]], [x for x in labels if name], "x" if row.get("name") else "y"]

def other_forms(name, row, user, buf, parts):
    heapq.heappush(parts, name)
    field = "full_name"
    class Holder:
        who = name
    match name:
        case str() as who:
            pass
    print("<p>Hi", "</p>", sep=name, file=buf)
    return ["<p>Hi X</p>".translate({88: name}), list(itertools.accumulate(["<p>Hi ", name]))[-1],
            f"{dict.get(row, 'name')}", row[field], Holder.who, textwrap.indent(name, "<p>Hi "),
            getattr("<p>Hi {}</p>", "format")(name), next(map(getattr, [user], ["full_name"]))]

def nested_preheader(text):
    def _preheader(text):
        return f'<div style="display:none">{text}</div>'
    return _preheader(text)

def held_builtins(name, holder, user, buf):
    put = setattr
    read = getattr
    say = print
    put(holder, "who", name)
    say(name, file=buf)
    return [f"<p>Hi {holder.who}</p>", f"<p>Hi {read(user, 'full_name')}</p>", buf.getvalue()]

def code_and_frames():
    import sys
    import inspect
    import importlib
    return [sys._getframe(0).f_locals, inspect.currentframe(), eval("1"), breakpoint, getattr(re, "sys"), exec("x = 1"),
            compile("1", "<probe>", "eval"), functools.__builtins__]

def branches(name, row):
    shown = _greeting(name if name else "there")
    return [shown, f"<p>{name if row else 'x'}</p>", name(), _greeting_text(name)]

class Echo(dict):
    def __missing__(self, key):
        return key

def echoed(name):
    return f"<p>Hi {Echo()[name]}</p>"

def held_scope(name):
    scope = locals
    return "<p>{}</p>".format(scope())

def held_by_name(user, field):
    read = getattr
    return f"<p>{read(user, field)}</p>"

def frame_read(name, error):
    return [f"<p>{error.__traceback__.tb_frame.f_locals}</p>", "<p>{0.tb_frame.f_locals}</p>".format(error.__traceback__),
            error.__traceback__.tb_frame.f_builtins]

def closure_read(name):
    def inner():
        return _greeting(name)
    return [f"<p>{inner.__closure__[0].cell_contents}</p>", _greeting.__globals__["__builtins__"], getattr(inner, "f_globals")]

def common_look_alikes(error, counts, seen, match, row, sender, user, value, name):
    add = seen.add
    card = row.get("partial")
    tags = [{"name": "category", "value": "alert"}, {"name": sender}]
    has = hasattr(user, "full_name")
    match value:
        case 1 if name:
            pass
    known = [name == "", name is None, name in ("a", "b"), "" != name, name in {"a"}]
    return [type(error).__name__, error.__class__.__name__, max(counts, key=counts.get), add, match.string, card, tags, has,
            known]

class Catch:
    def __eq__(self, other):
        Catch.held = other
        return False

def compared(name, box, other):
    if name == Catch():
        pass
    return [name in [box], name in box, other < name, f"<p>Hi {Catch.held}</p>"]

def field_paths(user, row):
    from string import Formatter as Fields
    return [f"<p>Hi {string.Formatter().get_field('0.full_name', [user], {})[0]}</p>", Fields, getattr(string, "Formatter")]

def frames_and_referents(frame):
    import traceback
    import gc
    return [traceback.walk_stack(None), gc.get_referents(frame), sys.modules["x"].traceback, frame.importlib,
            frame.builtins, frame.inspect, frame.gc, frame.operator, frame._operator]

def text_part_leaks(name):
    text_body = f"{_greeting_text(name)}\\n"
    page = f"<p>{text_body}</p>"
    print(text_body)
    send_email(html=_wrap_text(text_body), text=_wrap_text("x", text_body))
    pair = page, _wrap_text(text_body)
    return _wrap_text(text_body), _wrap_html(_wrap_text(text_body))

def text_part_kept(name, cache):
    text_body = f"{(greet := _greeting_text(name))}\\n"
    text_body = held = f"{_greeting_text(name)}\\n"
    kept = f"{_greeting_text(name)}\\n"
    cache.setdefault("g", _greeting_text(name))
    return [greet, held, f"<p>{dict(text=_wrap_text(text_body))['text']}</p>"]

def template_engines(user):
    import jinja2
    from mako.template import Template as Mako
    import chevron, pystache
    from django.template import engines
    Formatter = next(c for c in object.__subclasses__() if c.__name__ == "Formatter")
    return [jinja2.Template("<p>Hi {{ user.full_name }}</p>").render(user=user), Formatter().get_field("0.full_name", [user], {})[0],
            "<p>Hi {{ name }}</p>", "<p>Hi @name</p>", "<p>Hi <%= name %></p>", "row[name]", "{% if name %}x }",
            "<p>Hi #{name}</p> }", Mako, "<p>Hi {{ 1 > 0 and user|attr('full_name') }}</p>",
            "{% if x > 0 and name %}x }", "<% if x > 0 and name %>", "#{x > 0 and name} }", "<%\\n= name %>",
            "<p>Hi {{ '}' ~ user|attr('full_name') }}</p>", "<p>Hi {{ '}}' ~ user|attr('full_name') }}</p>",
            "{% if '%}' and name %}x }", "<% '%>' + name %>", "#{'}' + name} }", '{{ "}}" ~ user|attr("full_name") }}',
            '{% if "%}" and name %}x }', '<% "%>" + name %>', '#{"}" + name} }', "row['name']", "row[ name]", "@ name",
            "<p>Hi {{ {1: 2} and user|attr('full_name') }}</p>", "{% if x % 2 and name %}x }", "{% x {%} name %}x }"]

def engines_by_other_names(user, x):
    import starlette.templating as views
    from starlette.templating import Jinja2Templates, jinja2
    from fastapi import templating
    return [views.jinja2, x.templating, getattr(x, "vars"), getattr(x, "jinja2"), getattr(x, "getattr"), Jinja2Templates,
            x.mako, x.chevron, x.pystache, x.django]

def path_look_alikes(company_name):
    return ["support@example.com", "company_name", "the name of the filing", "Names", ".names", company_name,
            "Settings > Name", "{{ username }}", "<meta name=\\"viewport\\">", "@namecheap", "the name, {{ x }}"]

def names_after_a_block():
    return ["{{ x }} and the name", "{% x %} the name", "<% x %> the name", "#{x} the name", "{{ {1: {2: 3}} and name }}",
            "#{ {a: 1} && name }", "{{=| |=}} |name|", "{{ name }} {{ x }} #{y}"]

def imports_read(row):
    import html
    import re
    from app.config import settings
    from app.services.resend_service import send_email
    import html.parser
    import re as regex
    from html import escape
    from app.config import settings as config
    from . import pages
    from .app.config import settings
    return [html, re, settings, send_email, regex, escape, config, pages]

def patched(row, keep):
    html.escape = keep
    _greeting.__code__ = keep.__code__
    row.transport.send_email = keep
    del html.unescape
    html.escape += keep
    setattr(html, "escape", keep)
    delattr(html, "unescape")
    return [hasattr(row, "name"), getattr(html, "escape")]

def text_part_handed_on(name, keep):
    text_body = f"{keep:{_greeting_text(name)}}"
    text_body = f"{_greeting_text(name)}\\n" + keep
    text_body = keep + f"{_greeting_text(name)}\\n"
    text_body = f"{_greeting_text(name)}\\n" + ("a" + keep)
    text_body = f"{_greeting_text(name)}\\n" + (keep if keep else "")
    text_body = f"{_greeting_text(name)}\\n" + keep.join("x")
    text_body = f"{_greeting_text(name)}\\n" % "x"
    text_body = f"{_greeting_text(name)}\\n" + f"{keep}"
    text_body = f"{_greeting_text(name)}\\n" + "{}".format(keep)
    text_body = f"{_greeting_text(name)}\\n" + "{x}".format_map(keep)
    text_body = f"{keep}" + f"{_greeting_text(name)}\\n"
    text_body = f"{_greeting_text(name)}\\n" + f"{keep}".join("x")
    text_body = f"{_greeting_text(name)}\\n" + (f"{keep} more" if keep else "") + "\\n\\n".join(keep) + "end"
    text_body = f"{_greeting_text(name)}\\n" + f"- {keep}".strip()
    text_body = f"{_greeting_text(name)}\\n" + "".maketrans({"a": keep}).get(97)
    send_email(text=_wrap_text(text_body))

def text_part_str_methods(name, rows):
    text_body = (f"{_greeting_text(name)}\\n" + "x".capitalize() + "x".casefold() + "x".center(3) + "x".expandtabs(4)
                 + ", ".join(rows) + "x".ljust(3) + "x".lower() + "x".lstrip() + "x".removeprefix("y") + "x".removesuffix("y")
                 + "x".replace("x", "y") + "x".rjust(3) + "x".rstrip() + "x".strip() + "x".swapcase() + "x".title()
                 + "x".translate({}) + "x".upper() + "x".zfill(3) + " x ".strip().upper())
    send_email(text=_wrap_text(text_body))

def text_part_augmented(name, keep):
    text_body = f"{_greeting_text(name)}\\n"
    text_body += keep
    send_email(text=_wrap_text(text_body))

def imported_attributes(x, items):
    rows = [html.escape(x), re.compile("x", re.IGNORECASE | re.DOTALL), html.unescape(x), settings.FRONTEND_URL]
    rows_html = ""
    rows_html += f"<p>{html.escape(x)}</p>"
    return [rows, re.enum.bltns.locals(), html.parser, settings.__class__, send_email.__wrapped__, annotations.feature,
            getattr(html, "escape"), getattr(re, "enum"), rows_html]

def imports_read_whole(x):
    leak(re)
    held = html
    send_email(to=[x], html=x, text=x)
    return [settings, getattr(re, "compile"), held]

def typed(match: re.Match[str]) -> re.Pattern[str]:
    return match.re

def builtins_as_attributes(x, frame):
    return [len.__self__.locals(), x.vars(), x.globals(), x.setattr(x, "a", 1), x.exec("1"), x.compile("1"),
            x.__import__("os"), x.breakpoint, x.getattr(x, "a")]

def text_part_classed(name):
    class Kept:
        text_body = f"{_greeting_text(name)}\\n"
    return f"<p>{Kept.text_body}</p>"

def class_keywords(name):
    class Keyed(dict, name=name):
        pass
    return [Keyed, lambda who=name: who]
'''


def test_finder_catches_every_bypass_shape_and_accepts_the_helpers():
    assert _raw_name_sites(_FINDER_PROBE) == [
        ("<module>", "imports contextlib, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports functools, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports io, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports operator, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports string, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports deque from collections, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports partial from functools, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports wraps from functools, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports Template from string, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports functools as ft, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports string as st, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports * from contextlib, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports builtins, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports _operator, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports reduce from _functools, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports eval as run from builtins, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports sys as system from os, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("inner", "name read in an f-string, outside the greeting helpers"),
        ("_hidden_text", "hidden text built outside the module's _preheader()"),
        ("raw_fstring", "greeting built without _greeting()"),
        ("raw_fstring", "name read in an f-string, outside the greeting helpers"),
        ("escaped_inline", "greeting built without _greeting()"),
        ("escaped_inline", "name read as an argument to escape(), outside the greeting helpers"),
        ("concatenation", "full_name read in an operation, outside the greeting helpers"),
        ("percent_format", "name read in an operation, outside the greeting helpers"),
        ("str_format", "name read as an argument to format(), outside the greeting helpers"),
        ("raw_hidden_copy", "hidden text built outside the module's _preheader()"),
        ("raw_preheader", "hidden text built outside the module's _preheader()"),
        ("page_greets_as_typed", "_greeting_text() outside a text part (text_body = ...)"),
        ("wrapped_name", "full_name read as an argument to str(), outside the greeting helpers"),
        ("user_object", ".full_name read in an f-string, outside the greeting helpers"),
        ("joined", "name read into a collection, outside the greeting helpers"),
        ("concatenated_call", "name read as .title's receiver, outside the greeting helpers"),
        ("assigned_name", "name read into a variable, outside the greeting helpers"),
        ("assigned_chain", ".full_name read into a variable, outside the greeting helpers"),
        ("looped_name", "name read as .split's receiver, outside the greeting helpers"),
        ("stored_name", "name read into a variable, outside the greeting helpers"),
        ("keyed_lookup", "name read as a key a lookup takes, which a mapping can hand back, outside the greeting helpers"),
        ("augmented", "name read into a variable, outside the greeting helpers"),
        ("augmented_onto", ".full_name read as .strip's receiver, outside the greeting helpers"),
        ("percent_augmented", "%= fills a template the walk cannot read, or takes a modulo by what it does not read"),
        ("percent_augmented", "name read into a variable, outside the greeting helpers"),
        ("appended", "name read as an argument to append(), outside the greeting helpers"),
        ("extended", ".full_name read into a collection, outside the greeting helpers"),
        ("inserted", "name read as an argument to insert(), outside the greeting helpers"),
        ("updated", "name read as who= to update(), outside the greeting helpers"),
        ("defaulted", "name read as an argument to setdefault(), outside the greeting helpers"),
        ("added", "name read as an argument to add(), outside the greeting helpers"),
        ("mapped", "name read into a collection, outside the greeting helpers"),
        ("replaced", "name read as an argument to replace(), outside the greeting helpers"),
        ("looked_up", "'full_name' read in an f-string, outside the greeting helpers"),
        ("template_attribute", "a template field reads full_name, which a mapping fills without the name written"),
        ("template_keyword_attribute", "a template field reads name, which a mapping fills without the name written"),
        ("template_key", "a template field reads name, which a mapping fills without the name written"),
        ("template_mapping", "a template field reads name, which a mapping fills without the name written"),
        ("template_unpacked", "a template field reads full_name, which a mapping fills without the name written"),
        ("template_substituted", ".substitute() fills a template the walk cannot read"),
        ("template_substituted", "a template field reads name, which a mapping fills without the name written"),
        ("template_substituted", ".substitute() fills a template the walk cannot read"),
        ("template_substituted", "a template field reads full_name, which a mapping fills without the name written"),
        ("percent_mapping", "a template field reads name, which a mapping fills without the name written"),
        ("local_names", "a template field reads name, which a mapping fills without the name written"),
        ("local_names", "locals hands back a scope whole, which the walk does not follow"),
        ("object_names", "a template field reads full_name, which a mapping fills without the name written"),
        ("object_names", "vars hands back a scope whole, which the walk does not follow"),
        ("keyed_name", "'name' read in an f-string, outside the greeting helpers"),
        ("fetched_name", "'full_name' read in an f-string, outside the greeting helpers"),
        ("substituted", ".substitute() fills a template the walk cannot read"),
        ("substituted", "name read as who= to substitute(), outside the greeting helpers"),
        ("resubbed", "reads re.sub, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("resubbed", "name read as an argument to sub(), outside the greeting helpers"),
        ("appended_left", "name read as an argument to appendleft(), outside the greeting helpers"),
        ("written", "name read as an argument to write(), outside the greeting helpers"),
        ("set_attribute", "setattr() stores an attribute, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("set_attribute", "name read as an argument to setattr(), outside the greeting helpers"),
        ("set_item", ".__setitem__() calls an operator or a protocol by name, which the walk does not read"),
        ("set_item", "name read as an argument to __setitem__(), outside the greeting helpers"),
        ("a_field_named_so", "a template field reads name, which a mapping fills without the name written"),
        ("<module>", "a template field reads full_name, which a mapping fills without the name written"),
        ("auto_numbered", "a template field reads full_name, which a mapping fills without the name written"),
        ("auto_numbered", "a template field reads name, which a mapping fills without the name written"),
        ("held_template", "a template field reads full_name, which a mapping fills without the name written"),
        ("held_template", ".format() fills a template the walk cannot read"),
        ("held_template", ".format() fills a template the walk cannot read"),
        ("held_template", ".format_map() fills a template the walk cannot read"),
        ("held_percent", "a template field reads name, which a mapping fills without the name written"),
        ("held_percent", "% fills a template the walk cannot read, or takes a modulo by what it does not read"),
        ("held_percent", "%= fills a template the walk cannot read, or takes a modulo by what it does not read"),
        ("held_percent", "a template field reads name, which a mapping fills without the name written"),
        ("held_substitute", "a template field reads name, which a mapping fills without the name written"),
        ("held_substitute", ".substitute() fills a template the walk cannot read"),
        ("held_substitute", ".safe_substitute() fills a template the walk cannot read"),
        ("default_read", "'name' read in an f-string, outside the greeting helpers"),
        ("function_stores", "name read as an argument to setitem(), outside the greeting helpers"),
        ("function_stores", ".__setattr__() calls an operator or a protocol by name, which the walk does not read"),
        ("function_stores", "name read as an argument to __setattr__(), outside the greeting helpers"),
        ("function_stores", "name read as an argument to print(), outside the greeting helpers"),
        ("bytes_template", "% fills a template the walk cannot read, or takes a modulo by what it does not read"),
        ("fstring_templates", ".format() fills a template the walk cannot read"),
        ("fstring_templates", ".format_map() fills a template the walk cannot read"),
        ("fstring_templates", "% fills a template the walk cannot read, or takes a modulo by what it does not read"),
        ("fstring_templates", ".format() fills a template the walk cannot read"),
        ("fstring_templates", "% fills a template the walk cannot read, or takes a modulo by what it does not read"),
        ("operators_by_name", ".__add__() calls an operator or a protocol by name, which the walk does not read"),
        ("operators_by_name", "name read as an argument to __add__(), outside the greeting helpers"),
        ("operators_by_name", ".__mod__() calls an operator or a protocol by name, which the walk does not read"),
        ("operators_by_name", ".__mod__() calls an operator or a protocol by name, which the walk does not read"),
        ("operators_by_name", "a template field reads name, which a mapping fills without the name written"),
        ("operators_by_name", ".__mod__() calls an operator or a protocol by name, which the walk does not read"),
        ("unbound_stores", "name read as an argument to append(), outside the greeting helpers"),
        ("unbound_stores", "name read as who= to update(), outside the greeting helpers"),
        ("unbound_stores", "name read as an argument to add(), outside the greeting helpers"),
        ("held_by_dict", ".__dict__ hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("held_by_dict", "a template field reads __dict__, which hands on the values an object, a scope or a closure holds"),
        ("held_by_dict", "'name' read in an f-string, outside the greeting helpers"),
        ("nested_spec", "a template field reads full_name, which a mapping fills without the name written"),
        ("reached_by_name", "getattr() reaches an attribute by a name the walk does not read"),
        ("reached_by_name", "getattr() reaches an attribute by a name the walk does not read"),
        ("reached_by_name", "hasattr() reaches an attribute by a name the walk does not read"),
        ("reached_by_name", "delattr() deletes an attribute, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("unread_routes", "name read as an argument to print(), outside the greeting helpers"),
        ("unread_routes", "name read into a collection, outside the greeting helpers"),
        ("unread_routes", ".vformat() fills a template the walk cannot read"),
        ("unread_routes", ".Formatter may be string's, which reads a value by a field's path the walk does not read"),
        ("unread_routes", "name read into a collection, outside the greeting helpers"),
        ("unread_routes", "eval runs code the walk does not read"),
        ("unread_routes", "'name' read into a collection, outside the greeting helpers"),
        ("unread_routes", "globals hands back a scope whole, which the walk does not follow"),
        ("aliased_routes", "name read into a collection, outside the greeting helpers"),
        ("aliased_routes", ".Formatter may be string's, which reads a value by a field's path the walk does not read"),
        ("aliased_routes", "name read as an argument to what a call returns, outside the greeting helpers"),
        ("aliased_routes", "__import__ runs code the walk does not read"),
        ("aliased_routes", "a string names sys, which reaches what the walk does not follow"),
        ("reflected_routes", ".__dict__ hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("reflected_routes", "name read into a collection, outside the greeting helpers"),
        ("reflected_routes", ".__dict__ hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("reflected_routes", ".eval may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("reflected_routes", "'name' read into a collection, outside the greeting helpers"),
        ("reflected_routes", "__builtins__ runs code the walk does not read"),
        ("reflected_routes", "a string names eval, which reaches what the walk does not follow"),
        ("reflected_routes", "reads re.functools, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("reflected_routes", "name read into a collection, outside the greeting helpers"),
        ("reflected_routes", ".sys reaches the sys module through another name, which the walk does not follow"),
        ("reflected_routes", "getattr() reads re.functools, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("reflected_routes", "vars hands back a scope whole, which the walk does not follow"),
        ("reflected_routes", "re read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("reflected_routes", "reads re.__dict__, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("held_methods", ".format handed on uncalled, a template's filler the walk does not follow"),
        ("held_methods", "name read as an argument to fill(), outside the greeting helpers"),
        ("held_methods", "name read as an argument to put(), outside the greeting helpers"),
        ("held_methods", "'name' read into a collection, outside the greeting helpers"),
        ("held_methods", ".format handed on uncalled, a template's filler the walk does not follow"),
        ("held_methods", "name read into a collection, outside the greeting helpers"),
        ("handed_on", "name read as an argument to render(), outside the greeting helpers"),
        ("handed_on", "name read as who= to render(), outside the greeting helpers"),
        ("handed_on", "name read as name= to send_email(), outside the greeting helpers"),
        ("handed_on", "name read as name= to positional_only(), outside the greeting helpers"),
        ("handed_on", "name read as who= to card(), outside the greeting helpers"),
        ("handed_on", "name read as an argument to _greeting(), outside the greeting helpers"),
        ("tested", "name read in an assert, outside the greeting helpers"),
        ("tested", "name read in a comparison with what is no literal, whose __eq__ or __contains__ the module can define, outside the greeting helpers"),
        ("tested", "name read as a key a lookup takes, which a mapping can hand back, outside the greeting helpers"),
        ("tested", "'name' read as a key a lookup takes, which a mapping can hand back, outside the greeting helpers"),
        ("other_forms", "name read as an argument to heappush(), outside the greeting helpers"),
        ("other_forms", "'full_name' read into a variable, outside the greeting helpers"),
        ("Holder", "name read into a variable, outside the greeting helpers"),
        ("other_forms", "name read in a match, outside the greeting helpers"),
        ("other_forms", "name read as sep= to print(), outside the greeting helpers"),
        ("other_forms", "name read into a collection, outside the greeting helpers"),
        ("other_forms", "name read into a collection, outside the greeting helpers"),
        ("other_forms", "'name' read in an f-string, outside the greeting helpers"),
        ("other_forms", "name read as an argument to indent(), outside the greeting helpers"),
        ("other_forms", "getattr() reaches format, which the walk does not follow"),
        ("other_forms", "name read as an argument to what a call returns, outside the greeting helpers"),
        ("other_forms", "getattr handed on uncalled, which reaches an attribute by a name the walk does not read"),
        ("other_forms", "'full_name' read into a collection, outside the greeting helpers"),
        ("nested_preheader", "binds _preheader again, so a call of it may reach other code than the function the walk reads"),
        ("_preheader", "hidden text built outside the module's _preheader()"),
        ("held_builtins", "setattr handed on uncalled, which reaches an attribute by a name the walk does not read"),
        ("held_builtins", "getattr handed on uncalled, which reaches an attribute by a name the walk does not read"),
        ("held_builtins", "name read as an argument to put(), outside the greeting helpers"),
        ("held_builtins", "name read as an argument to say(), outside the greeting helpers"),
        ("held_builtins", "'full_name' read in an f-string, outside the greeting helpers"),
        ("code_and_frames", "imports sys, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("code_and_frames", "imports inspect, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("code_and_frames", "imports importlib, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("code_and_frames", ".f_locals hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("code_and_frames", "eval runs code the walk does not read"),
        ("code_and_frames", "breakpoint runs code the walk does not read"),
        ("code_and_frames", "getattr() reads re.sys, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("code_and_frames", "exec runs code the walk does not read"),
        ("code_and_frames", "compile runs code the walk does not read"),
        ("code_and_frames", "a string names eval, which reaches what the walk does not follow"),
        ("code_and_frames", ".__builtins__ hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("branches", "name read in an f-string, outside the greeting helpers"),
        ("branches", "name read as what a call calls, outside the greeting helpers"),
        ("branches", "_greeting_text() outside a text part (text_body = ...)"),
        ("echoed", "name read as a key a lookup takes, which a mapping can hand back, outside the greeting helpers"),
        ("held_scope", "locals hands back a scope whole, which the walk does not follow"),
        ("held_by_name", "getattr handed on uncalled, which reaches an attribute by a name the walk does not read"),
        ("frame_read", ".f_locals hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("frame_read", "a template field reads f_locals, which hands on the values an object, a scope or a closure holds"),
        ("frame_read", ".f_builtins hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("closure_read", ".cell_contents hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("closure_read", ".__closure__ hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("closure_read", ".__globals__ hands on the values an object, a scope or a closure holds, a name among them, which the walk does not follow"),
        ("closure_read", "a string names __builtins__, which reaches what the walk does not follow"),
        ("closure_read", "getattr() reaches f_globals, which the walk does not follow"),
        ("__eq__", "stores .held, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("compared", "name read in a comparison with what is no literal, whose __eq__ or __contains__ the module can define, outside the greeting helpers"),
        ("compared", "name read in a comparison with what is no literal, whose __eq__ or __contains__ the module can define, outside the greeting helpers"),
        ("compared", "name read in a comparison with what is no literal, whose __eq__ or __contains__ the module can define, outside the greeting helpers"),
        ("compared", "name read in a comparison with what is no literal, whose __eq__ or __contains__ the module can define, outside the greeting helpers"),
        ("field_paths", "imports Formatter as Fields from string, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("field_paths", ".Formatter may be string's, which reads a value by a field's path the walk does not read"),
        ("field_paths", "a string reads full_name by a path or after a template block's opener, which the walk does not parse"),
        ("field_paths", "getattr() reaches Formatter, which the walk does not follow"),
        ("frames_and_referents", "imports traceback, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("frames_and_referents", "imports gc, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("frames_and_referents", ".traceback reaches the traceback module through another name, which the walk does not follow"),
        ("frames_and_referents", ".importlib reaches the importlib module through another name, which the walk does not follow"),
        ("frames_and_referents", ".builtins reaches the builtins module through another name, which the walk does not follow"),
        ("frames_and_referents", ".inspect reaches the inspect module through another name, which the walk does not follow"),
        ("frames_and_referents", ".gc reaches the gc module through another name, which the walk does not follow"),
        ("frames_and_referents", ".operator reaches the operator module through another name, which the walk does not follow"),
        ("frames_and_referents", "._operator reaches the _operator module through another name, which the walk does not follow"),
        ("text_part_leaks", "text_body read but as _wrap_text()'s text, though it holds the name as typed"),
        ("text_part_leaks", "text_body read but as _wrap_text()'s text, though it holds the name as typed"),
        ("text_part_leaks", "_wrap_text() stands where its value is no text part (send_email's text=, a returned tuple's last element)"),
        ("text_part_leaks", "text_body read but as _wrap_text()'s text, though it holds the name as typed"),
        ("text_part_leaks", "_wrap_text() stands where its value is no text part (send_email's text=, a returned tuple's last element)"),
        ("text_part_leaks", "_wrap_text() stands where its value is no text part (send_email's text=, a returned tuple's last element)"),
        ("text_part_leaks", "_wrap_text() stands where its value is no text part (send_email's text=, a returned tuple's last element)"),
        ("text_part_kept", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_kept", "_greeting_text() outside a text part (text_body = ...)"),
        ("text_part_kept", "_greeting_text() outside a text part (text_body = ...)"),
        ("text_part_kept", "_greeting_text() outside a text part (text_body = ...)"),
        ("text_part_kept", "_wrap_text() stands where its value is no text part (send_email's text=, a returned tuple's last element)"),
        ("template_engines", "imports jinja2, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("template_engines", "imports Template as Mako from mako.template, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("template_engines", "imports chevron, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("template_engines", "imports pystache, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("template_engines", "imports engines from django.template, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("template_engines", "Formatter may be string's, which reads a value by a field's path the walk does not read"),
        ("template_engines", "a string names Formatter, which reaches what the walk does not follow"),
        ("template_engines", "a string reads full_name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "Formatter may be string's, which reads a value by a field's path the walk does not read"),
        ("template_engines", "a string reads full_name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads full_name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads full_name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads full_name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads full_name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads full_name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("template_engines", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("engines_by_other_names", "imports starlette.templating as views, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("engines_by_other_names", "imports Jinja2Templates from starlette.templating, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("engines_by_other_names", "imports jinja2 from starlette.templating, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("engines_by_other_names", "imports templating from fastapi, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("engines_by_other_names", ".jinja2 reaches a template engine through another name, whose templates the walk does not read"),
        ("engines_by_other_names", ".templating reaches a template engine through another name, whose templates the walk does not read"),
        ("engines_by_other_names", "getattr() reaches vars, which the walk does not follow"),
        ("engines_by_other_names", "getattr() reaches jinja2, which the walk does not follow"),
        ("engines_by_other_names", "getattr() reaches getattr, which the walk does not follow"),
        ("engines_by_other_names", ".mako reaches a template engine through another name, whose templates the walk does not read"),
        ("engines_by_other_names", ".chevron reaches a template engine through another name, whose templates the walk does not read"),
        ("engines_by_other_names", ".pystache reaches a template engine through another name, whose templates the walk does not read"),
        ("engines_by_other_names", ".django reaches a template engine through another name, whose templates the walk does not read"),
        ("names_after_a_block", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("names_after_a_block", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("names_after_a_block", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("names_after_a_block", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("names_after_a_block", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("names_after_a_block", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("names_after_a_block", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("names_after_a_block", "a string reads name by a path or after a template block's opener, which the walk does not parse"),
        ("imports_read", "imports html.parser, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("imports_read", "binds html, which an allowed import binds: the walk reads the name only as that import"),
        ("imports_read", "imports re as regex: the walk reads an allowed import only as written"),
        ("imports_read", "imports escape from html, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("imports_read", "imports settings as config from app.config: the walk reads an allowed import only as written"),
        ("imports_read", "imports pages from ., which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("imports_read", "imports settings from .app.config, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("imports_read", "binds settings, which an allowed import binds: the walk reads the name only as that import"),
        ("imports_read", "html read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("imports_read", "re read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("imports_read", "settings read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("imports_read", "send_email read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("patched", "stores .escape, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("patched", "stores .__code__, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("patched", "stores .send_email, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("patched", "deletes .unescape, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("patched", "stores .escape, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("patched", "setattr() stores an attribute, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("patched", "html read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("patched", "delattr() deletes an attribute, which may rebind a name the walk trusts or patch an object a helper calls"),
        ("patched", "html read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_handed_on", "_greeting_text() stands in its text part where its text may go elsewhere than the string: a format spec, a binding, or beside what the language does not build alone"),
        ("text_part_augmented", "text_body augmented, which reads the text and hands it to the other operand's code"),
        ("imported_attributes", ".locals may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("imported_attributes", "reads re.enum, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("imported_attributes", "reads html.parser, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("imported_attributes", "reads settings.__class__, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("imported_attributes", "reads send_email.__wrapped__, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("imported_attributes", "reads annotations.feature, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("imported_attributes", "getattr() reads re.enum, an attribute of an allowed import the walk does not read (_IMPORTS)"),
        ("imports_read_whole", "re read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("imports_read_whole", "html read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("imports_read_whole", "settings read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("builtins_as_attributes", ".locals may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("builtins_as_attributes", ".vars may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("builtins_as_attributes", ".globals may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("builtins_as_attributes", ".setattr may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("builtins_as_attributes", ".exec may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("builtins_as_attributes", ".compile may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("builtins_as_attributes", ".__import__ may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("builtins_as_attributes", ".breakpoint may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("builtins_as_attributes", ".getattr may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("Kept", "_greeting_text() outside a text part (text_body = ...)"),
        ("Keyed", "name read as name= to a class, outside the greeting helpers"),
        ("class_keywords", "name read as a default, outside the greeting helpers"),
    ]


# A greeting helper or a function the walk hands a name to, bound again: each binding fails, as a call of it may then
# reach other code; a decorated helper fails, and a decorated function takes no name= the walk follows.
_REBOUND_PROBE = '''
import functools
import html
from app.pages import render_page as render
from app.pages import *
import app.pages as render

def _greeting_text(name):
    return f"Hi {name}," if name else "Hi there,"

@functools.cache
def _greeting(name):
    return html.escape(_greeting_text(name))

def render(name):
    greeting = _greeting(name)
    return f"<p>{greeting}</p>"

@functools.cache
def render_card(name):
    return _greeting(name)

_PAGES = []

def _wrap_text(text, footer=""):
    _PAGES.append(text)
    return f"{text}{footer}"

def hasattr(row, key):
    return row[key]

class Rows:
    def hasattr(row, key):
        return row[key]

class send_email:
    pass

html = None
_LINE_SEPARATORS = None
_LINE_SEPARATORS = keep
max = min
[(html := 1) for _ in []]
[(_LINE_SEPARATORS := 1) for _ in []]
[_LINE_SEPARATORS for _LINE_SEPARATORS in []]
shadow = lambda _LINE_SEPARATORS: _LINE_SEPARATORS

class Kept:
    _LINE_SEPARATORS = None

def _unused(x=(_LINE_SEPARATORS := keep), *, y=(max := min)):
    return x

defaulted = lambda x=(_LINE_SEPARATORS := keep): x

@(lambda f: f) if (_LINE_SEPARATORS := keep) else None
def decorated():
    pass

class Based((_LINE_SEPARATORS := keep).__class__, metaclass=(_LINE_SEPARATORS := keep)):
    pass

def annotated(x: (_LINE_SEPARATORS := keep)) -> (_LINE_SEPARATORS := keep):
    pass

def parameter(_LINE_SEPARATORS=None):
    return _LINE_SEPARATORS

def outer():
    def inner(x=(_LINE_SEPARATORS := keep)):
        return x
    return inner

def local_html(page):
    html = page
    import re as html
    return html

def trusted(row):
    send_email = print
    return [hasattr(row, "name"), Rows.hasattr(row, "full_name"), f"<p>{_PAGES[0]}</p>", send_email]

from elsewhere import keep as _wrap_text

def _wrap_text(text, footer=""):
    _PAGES.append(text)
    return f"{text}{footer}"
from elsewhere import send_email
from app.services.resend_service import deliver as send_email

def card(name, _greeting):
    return [_greeting(name), render_card(name=name)]

def shadowed(name):
    def _greeting(name):
        return f"<p>{name}</p>"
    return [_greeting(name), render(name=name)]

def assigned(name):
    global render
    render = lambda name: f"<p>{name}</p>"
    return render(name=name)

def captured(value):
    try:
        pass
    except ValueError as render:
        pass
    match value:
        case [*render]:
            pass
        case {"x": 1, **render}:
            pass
        case str() as render:
            pass

def _greeting_text(name):
    return f"<p>{name}</p>"
'''


# _wrap_text and _preheader however written, each the first def of a module of its own: the walk holds the text by
# _wrap_text's first positional parameter anywhere in it, built as a text part is, and refuses a helper decorated, an
# async one, or one that takes no such parameter.
_WRAPPERS = {
    'def _wrap_text(text, footer=""):\n    return f"{text}\\n\\n{footer}"\n': [],
    'def _wrap_text(text, footer=""):\n    def keep():\n        _PAGES.append(text)\n    return f"{text}{footer}"\n': [
        ("keep", "_wrap_text reads its text elsewhere than in the string it returns"),
    ],
    'def _wrap_text(text, footer=""):\n    def keep():\n        return f"{text}"\n    _PAGES.append(keep)\n    return f"{text}{footer}"\n': [
        ("keep", "_wrap_text reads its text elsewhere than in the string it returns"),
    ],
    'def _wrap_text(text, footer=""):\n    text += footer\n    return f"{text}"\n': [
        ("_wrap_text", "text augmented, which reads the text and hands it to the other operand's code"),
    ],
    'def _wrap_text(text, footer=""):\n    return f"{text}" + f"{footer}"\n': [
        ("_wrap_text", "_wrap_text reads its text elsewhere than in the string it returns"),
    ],
    'def _wrap_text(text, footer=""):\n    return f"{text}\\n" + f"{footer}".strip()\n': [
        ("_wrap_text", "_wrap_text reads its text elsewhere than in the string it returns"),
    ],
    'def _wrap_text(text, footer=""):\n    return f"{text}\\n" + f"- {footer}".strip()\n': [],
    'def _wrap_text(text, footer=""):\n    return f"{text}\\n" + "".maketrans({"a": footer}).get(97)\n': [
        ("_wrap_text", "_wrap_text reads its text elsewhere than in the string it returns"),
    ],
    'def _wrap_text(text, /, footer=""):\n    _PAGES.append(text)\n    return f"{text}{footer}"\n': [
        ("_wrap_text", "_wrap_text reads its text elsewhere than in the string it returns"),
    ],
    'def _wrap_text(text, footer=""):\n    return text + footer\n': [
        ("_wrap_text", "_wrap_text reads its text elsewhere than in the string it returns"),
    ],
    'def _wrap_text(text, footer=""):\n    return f"{footer:{text}}{text}"\n': [
        ("_wrap_text", "_wrap_text reads its text elsewhere than in the string it returns"),
    ],
    '@spy\ndef _wrap_text(text, footer=""):\n    return f"{text}{footer}"\n': [
        ("<module>", "decorates _wrap_text, so a call of it may reach other code than the helper's body"),
    ],
    '@spy\ndef _preheader(text):\n    return f"<div style=\\"display:none\\">{text}</div>"\n': [
        ("<module>", "decorates _preheader, so a call of it may reach other code than the helper's body"),
    ],
    'def _wrap_text(*parts):\n    return "".join(parts)\n': [
        ("<module>", "_wrap_text takes its text by no positional parameter of a plain def, so the walk cannot hold it"),
    ],
    'async def _wrap_text(text, footer=""):\n    return f"{text}{footer}"\n': [
        ("<module>", "_wrap_text takes its text by no positional parameter of a plain def, so the walk cannot hold it"),
    ],
}


def test_finder_holds_the_wrapper_however_it_is_written():
    assert {source: _raw_name_sites(source) for source in _WRAPPERS} == _WRAPPERS


def test_finder_refuses_a_followed_function_bound_again():
    assert _raw_name_sites(_REBOUND_PROBE) == [
        ("<module>", "imports functools, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports render_page as render from app.pages, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "binds render again, so a call of it may reach other code than the function the walk reads"),
        ("<module>", "imports * from app.pages, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "imports app.pages as render, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "binds render again, so a call of it may reach other code than the function the walk reads"),
        ("<module>", "decorates _greeting, so a call of it may reach other code than the helper's body"),
        ("<module>", "binds render again at the module's top, so a helper that reads it may read another value"),
        ("_wrap_text", "_wrap_text reads its text elsewhere than in the string it returns"),
        ("<module>", "binds hasattr, which the walk trusts as the builtin"),
        ("Rows", "binds hasattr, which the walk trusts as the builtin"),
        ("<module>", "binds send_email otherwise than from app.services.resend_service, the import the walk trusts"),
        ("<module>", "binds html, which an allowed import binds: the walk reads the name only as that import"),
        ("<module>", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("<module>", "binds max, a builtin's name, at the module's top, so a helper that reads the builtin may read another value"),
        ("<module>", "binds html, which an allowed import binds: the walk reads the name only as that import"),
        ("<module>", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("_unused", "binds max again at the module's top, so a helper that reads it may read another value"),
        ("_unused", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("<module>", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("decorated", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("Based", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("Based", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("annotated", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("annotated", "binds _LINE_SEPARATORS again at the module's top, so a helper that reads it may read another value"),
        ("local_html", "binds html, which an allowed import binds: the walk reads the name only as that import"),
        ("local_html", "imports re as html: the walk reads an allowed import only as written"),
        ("local_html", "binds html, which an allowed import binds: the walk reads the name only as that import"),
        ("local_html", "html read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("trusted", "binds send_email otherwise than from app.services.resend_service, the import the walk trusts"),
        ("trusted", ".hasattr may be the builtin, which hands back a scope, runs code or reaches an attribute by a name, through another object"),
        ("trusted", "'full_name' read into a collection, outside the greeting helpers"),
        ("trusted", "send_email read whole, so its attributes are read where the walk does not read them (_IMPORTS)"),
        ("<module>", "imports keep as _wrap_text from elsewhere, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "binds _wrap_text again, so a call of it may reach other code than the function the walk reads"),
        ("<module>", "binds _wrap_text again, so a call of it may reach other code than the function the walk reads"),
        ("<module>", "imports send_email from elsewhere, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "binds send_email otherwise than from app.services.resend_service, the import the walk trusts"),
        ("<module>", "imports deliver as send_email from app.services.resend_service, which the walk does not read: a module may run code, reach a frame, patch an object or fill a template unseen"),
        ("<module>", "binds send_email otherwise than from app.services.resend_service, the import the walk trusts"),
        ("card", "binds _greeting again, so a call of it may reach other code than the function the walk reads"),
        ("card", "name read as name= to render_card(), outside the greeting helpers"),
        ("shadowed", "binds _greeting again, so a call of it may reach other code than the function the walk reads"),
        ("_greeting", "name read in an f-string, outside the greeting helpers"),
        ("assigned", "declares render global, so a function may rebind a name the module's helpers read"),
        ("assigned", "binds render again, so a call of it may reach other code than the function the walk reads"),
        ("assigned", "name read in an f-string, outside the greeting helpers"),
        ("captured", "binds render again, so a call of it may reach other code than the function the walk reads"),
        ("captured", "binds render again, so a call of it may reach other code than the function the walk reads"),
        ("captured", "binds render again, so a call of it may reach other code than the function the walk reads"),
        ("captured", "binds render again, so a call of it may reach other code than the function the walk reads"),
        ("<module>", "binds _greeting_text again, so a call of it may reach other code than the function the walk reads"),
        ("_greeting_text", "name read in an f-string, outside the greeting helpers"),
    ]


def test_email_service_routes_every_name_through_the_helpers():
    found = set(_raw_name_sites(MODULE.read_text(encoding="utf-8")))
    unexpected = found - ALLOWED_SITES
    assert not unexpected, (
        "app/services/email_service.py interpolates a recipient's name outside the escaping helpers:\n"
        + "\n".join(f"  {function}(): {offence}" for function, offence in sorted(unexpected))
        + "\nUse `greeting = _greeting(name)` for the page's salutation, `_greeting_text(name)` in `text_body = ...` for the text part's, "
        "`_wrap_html(..., preheader=line)` for the preheader, and hand the text part to send_email as `text=` "
        "rather than hiding a copy in the page. An import the walk reads joins _IMPORTS with what it is for; extending "
        "ALLOWED_SITES needs a written reason next to the entry."
    )
    stale = ALLOWED_SITES - found
    assert not stale, f"Sanctioned sites no longer bypass the helpers — delete them: {sorted(stale)}"


def test_helpers_are_defined_in_the_module():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {GREETING_HELPER, GREETING_TEXT_HELPER, TEXT_WRAPPER, *HIDDEN_TEXT_HELPERS} <= defined
