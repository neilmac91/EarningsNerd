"""Every link the backend builds on ``FRONTEND_URL`` leads to something the frontend serves.

E46 (2): the waitlist's welcome mail asked its reader to verify through
``{FRONTEND_URL}/api/waitlist/verify/{token}``, a path no frontend route served (a GET answered 404 on
www), so the step it asked for could not be taken.

The scan reads every ``FRONTEND_URL`` read in ``backend/app``: ``<anything>.FRONTEND_URL``, the same
through ``.rstrip(...)`` or ``.strip(...)`` or alone in an f-string, or a name assigned from one of those
(an alias). Names resolve by Python's scope rules: a module's alias is seen in its functions, and a
function's in the functions, lambdas and comprehensions inside it, unless a scope binds the name itself;
a class body is a scope of its own that its methods do not see; ``global`` and ``nonlocal`` bind where
the name lives; defaults, annotations and decorators resolve in the enclosing scope. Each read must be
followed, or the gate fails:

- a replacement field of an f-string: the link's path is the text after it;
- the left end of a ``+`` chain: the path is the chain's other operands, joined;
- the value an alias is assigned in a module or a function: the alias's reads are followed in turn, a
  walrus's value is followed where it stands as well, and a module's alias that the module never reads
  fails, as it can only be meant for another module;
- a bare origin, passed whole to a call, returned, or one side of ``or``, in a function ``BARE_ORIGINS``
  lists with its count of such reads and its reason: the home page.

An alias its scope also binds another way (another value, ``+=``, a loop's target) is read by name, not
by flow, so its reads fail as unfollowed. A path runs to the first ``? # " ' < >`` or space, and an empty
one is the home page. A spliced value stands for a segment and takes only a ``[param]`` directory; a
module constant spliced in, assigned once (annotated or not), is read as its value unless the scope
binds the name. A path that does not start with ``/`` once read (a spliced value first, an imported
name) fails as unreadable. The path resolves against ``frontend/app``: a directory holding a ``page``
file, or a ``route`` file that exports ``GET`` outside a comment; a route group ``(name)`` adds no
segment; a ``_private`` folder is never matched, nor a parallel-route slot ``@name`` (a hard load, as a
mail's link is, does not serve a slot's page at its URL); a catch-all takes the rest, an optional one
also none. Or it resolves against ``frontend/public``: a file.

Gaps, planted in ``test_the_scan_follows_each_form_and_fails_closed``: an alias a module defines and also
reads, which another module imports (the use there is not read); the origin taken by ``getattr`` with the
setting's name as a string. Not served, so a link to one fails: Next's metadata routes (``sitemap.ts`` as
``/sitemap.xml``, ``robots.ts``, ``manifest.ts``, ``opengraph-image``, ``icon``), and a path that
``middleware.ts`` or ``next.config.js`` would serve without a page (the config sets headers only).
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_APP = ROOT / "backend" / "app"
FRONTEND_APP = ROOT / "frontend" / "app"
FRONTEND_PUBLIC = ROOT / "frontend" / "public"
PAGE_FILES = ("page.tsx", "page.ts", "page.jsx", "page.js", "page.mdx")
ROUTE_FILES = ("route.ts", "route.tsx", "route.js")
# A value the code splices into a path: it stands only where a [param] directory does.
SPLICE = "\x00"
_URL_END = re.compile(r"[?#\"'<>\s]")
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_NESTED = (*_FUNCTIONS, *_COMPREHENSIONS, ast.ClassDef)
_STRIPS = ("rstrip", "strip")

# The bare origin, as the home page, where it stands: (module, function) -> (how many reads, why).
BARE_ORIGINS = {
    ("backend/app/routers/auth.py", "google_callback"): (1, "a reader Google signs in lands on the home page"),
    ("backend/app/routers/auth.py", "apple_callback"): (1, "a reader Apple signs in lands on the home page"),
    ("backend/app/services/email_service.py", "_filing_url"): (1, "an alert with no filing page of ours links the home page"),
}


@dataclass
class _Scope:
    node: ast.AST
    parent: _Scope | None  # where its free names resolve: a class body is not on a method's chain
    bound: set[str]
    globals_: set[str]
    nonlocals: set[str]
    aliases: set[str] = field(default_factory=set)  # names bound here to the origin
    rebound: set[str] = field(default_factory=set)  # names bound here another way too


@dataclass
class Scan:
    links: list[tuple[int, str]] = field(default_factory=list)  # (line of the read, path)
    unfollowed: list[tuple[int, str]] = field(default_factory=list)  # (line, enclosing function)
    bare: list[tuple[int, str]] = field(default_factory=list)  # (line, enclosing function)


def _own_nodes(scope: ast.AST):
    """The nodes of ``scope``, not descending into the functions, comprehensions and classes in it."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _NESTED):
            stack.extend(ast.iter_child_nodes(node))


def _binds(scope: ast.AST) -> tuple[set[str], set[str], set[str]]:
    """The names ``scope`` binds itself, and those it declares global and nonlocal."""
    names: set[str] = set()
    if isinstance(scope, _FUNCTIONS):
        args = scope.args
        names |= {arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg) if arg}
    globals_: set[str] = set()
    nonlocals: set[str] = set()
    for node in _own_nodes(scope):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        elif isinstance(node, ast.Global):
            globals_ |= set(node.names)
        elif isinstance(node, ast.Nonlocal):
            nonlocals |= set(node.names)
    return names - globals_ - nonlocals, globals_, nonlocals


def _innermost(name: str, scope: _Scope | None) -> _Scope | None:
    """The scope a name read in ``scope`` resolves to."""
    while scope is not None:
        if name in scope.bound:
            return scope
        scope = scope.parent
    return None


def _alias_targets(node: ast.AST | None) -> list[str] | None:
    """The names an assignment binds, if it binds only names; None for any other target."""
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
        targets = [node.target]
    else:
        return None
    return [target.id for target in targets] if all(isinstance(target, ast.Name) for target in targets) else None


def _lone_field(node: ast.AST) -> ast.AST | None:
    """The value of an f-string that is one field and nothing else, written as itself; else None."""
    if isinstance(node, ast.JoinedStr) and len(node.values) == 1:
        part = node.values[0]
        if isinstance(part, ast.FormattedValue) and part.format_spec is None and part.conversion in (-1, ord("s")):
            return part.value
    return None


def _text(part: ast.AST, scope: _Scope, constants: dict[str, str]) -> str:
    if isinstance(part, ast.Constant) and isinstance(part.value, str):
        return part.value
    if isinstance(part, ast.FormattedValue):
        return _text(part.value, scope, constants)
    if isinstance(part, ast.JoinedStr):
        return "".join(_text(value, scope, constants) for value in part.values)
    if isinstance(part, ast.Name):
        owner = _innermost(part.id, scope)
        if owner is not None and owner.parent is None and part.id in constants:
            return constants[part.id]
    return SPLICE


def _path(parts: list[ast.AST], scope: _Scope, constants: dict[str, str]) -> str:
    """The path a link's text after the origin names: "/" for none, as read otherwise."""
    text = "".join(_text(part, scope, constants) for part in parts)
    return _URL_END.split(text, maxsplit=1)[0] or "/"


def scan_module(source: str, module: str) -> Scan:
    """Follow every read of the frontend's origin in ``source``, the module at ``module``."""
    if "FRONTEND_URL" not in source:
        return Scan()  # it reads none: an alias imported from elsewhere is the planted gap
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    stores = Counter(node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store))
    constants = {
        name: node.value.value
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        for name in _alias_targets(node) or []
        if stores[name] == 1
    }
    scopes: dict[ast.AST, _Scope] = {}

    def owner_of(name: str, scope: _Scope) -> _Scope | None:
        """The scope a binding of ``name`` made in ``scope`` lands in."""
        if name in scope.globals_:
            return scopes[tree]
        if name in scope.nonlocals:
            return _innermost(name, scope.parent)
        return scope

    def origin(node: ast.AST | None, scope: _Scope) -> bool:
        """True if ``node`` is the frontend's origin: a read of it, stripped, wrapped alone, or an alias."""
        if isinstance(node, ast.Attribute):
            return node.attr == "FRONTEND_URL" and isinstance(node.ctx, ast.Load)
        if isinstance(node, ast.Name):
            owner = _innermost(node.id, scope)
            return isinstance(node.ctx, ast.Load) and owner is not None and node.id in owner.aliases
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _STRIPS:
            return origin(node.func.value, scope)
        inner = _lone_field(node) if node is not None else None
        return inner is not None and origin(inner, scope)

    def build(node: ast.AST, parent: _Scope | None) -> None:
        bound, globals_, nonlocals = _binds(node)
        scope = _Scope(node, parent, bound, globals_, nonlocals)
        scopes[node] = scope
        own = list(_own_nodes(node))
        if not isinstance(node, ast.ClassDef):  # a class attribute's uses are not names: it never is an alias
            grown = True
            while grown:  # an alias may be assigned from another alias
                grown = False
                for statement in own:
                    names = _alias_targets(statement)
                    if names and origin(statement.value, scope):
                        for name in names:
                            owner = owner_of(name, scope)
                            if owner is not None and name not in owner.aliases:
                                owner.aliases.add(name)
                                grown = True
        for inner in own:
            if isinstance(inner, ast.ClassDef):
                build(inner, parent=scope)
                scopes[inner].parent = scope  # the class body resolves through the scope around it
            elif isinstance(inner, (*_FUNCTIONS, *_COMPREHENSIONS)):
                around = scope
                while isinstance(around.node, ast.ClassDef):
                    around = around.parent
                build(inner, parent=around)

    build(tree, None)

    def is_origin_binding(name_node: ast.Name, scope: _Scope) -> bool:
        statement = parents.get(name_node)
        return _alias_targets(statement) is not None and name_node in getattr(statement, "targets", [getattr(statement, "target", None)]) and origin(statement.value, scope)

    for scope in list(scopes.values()):  # a name bound to the origin and another way is ambiguous
        for node in _own_nodes(scope.node):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                parent = parents.get(node)
                if isinstance(parent, ast.AnnAssign) and parent.value is None:
                    continue
                if not is_origin_binding(node, scope):
                    owner = owner_of(node.id, scope)
                    if owner is not None:
                        owner.rebound.add(node.id)
        if isinstance(scope.node, _FUNCTIONS):
            scope.rebound |= scope.aliases & {arg.arg for arg in ast.walk(scope.node.args) if isinstance(arg, ast.arg)}

    def scope_of(node: ast.AST) -> _Scope:
        child, up = node, parents.get(node)
        while up is not None and up not in scopes:
            child, up = up, parents.get(up)
        if up is None:
            return scopes[tree]
        outside = (
            (isinstance(up, _FUNCTIONS) and (child is up.args or child is getattr(up, "returns", None)))
            or (isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child in up.decorator_list)
            or (isinstance(up, ast.ClassDef) and (child in up.bases or child in up.keywords))
        )
        return scopes[up].parent if outside and scopes[up].parent is not None else scopes[up]

    def function_of(node: ast.AST) -> str:
        up = parents.get(node)
        while up is not None and not isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef)):
            up = parents.get(up)
        return up.name if up is not None else "<module>"

    reads: list[tuple[ast.AST, _Scope]] = []
    alias_reads: Counter = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "FRONTEND_URL" and isinstance(node.ctx, ast.Load):
            reads.append((node, scope_of(node)))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            scope = scope_of(node)
            owner = _innermost(node.id, scope)
            if owner is not None and node.id in owner.aliases:
                reads.append((node, scope))
                alias_reads[(id(owner), node.id)] += 1

    result = Scan()
    for node, scope in reads:
        if isinstance(node, ast.Name):
            owner = _innermost(node.id, scope)
            if node.id in owner.rebound:
                result.unfollowed.append((node.lineno, function_of(node)))
                continue
        expression = node
        while True:
            while True:  # through a strip of it, or an f-string that holds it alone
                up = parents.get(expression)
                if isinstance(up, ast.Attribute) and up.attr in _STRIPS and isinstance(parents.get(up), ast.Call) and parents[up].func is up:
                    expression = parents[up]
                elif isinstance(up, ast.FormattedValue) and _lone_field(parents.get(up)) is expression:
                    expression = parents[up]
                else:
                    break
            up = parents.get(expression)
            names = _alias_targets(up)
            if isinstance(up, ast.FormattedValue) and isinstance(parents.get(up), ast.JoinedStr):
                values = parents[up].values
                result.links.append((node.lineno, _path(values[values.index(up) + 1:], scope, constants)))
            elif isinstance(up, ast.BinOp) and isinstance(up.op, ast.Add) and up.left is expression:
                rest: list[ast.AST] = []
                chain = up
                while True:
                    rest.append(chain.right)
                    parent = parents.get(chain)
                    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add) and parent.left is chain:
                        chain = parent
                    else:
                        break
                result.links.append((node.lineno, _path(rest, scope, constants)))
            elif names and up.value is expression and not isinstance(scope.node, ast.ClassDef) and all(
                (owner := owner_of(name, scope)) is not None and name in owner.aliases
                and (owner.parent is not None or alias_reads[(id(owner), name)] > 0)
                for name in names
            ):
                if isinstance(up, ast.NamedExpr):  # its value is also used where the walrus stands
                    expression = up
                    continue
            elif (module, function_of(node)) in BARE_ORIGINS and (
                isinstance(up, (ast.keyword, ast.Return))
                or (isinstance(up, ast.BoolOp) and isinstance(up.op, ast.Or))
                or (isinstance(up, ast.Call) and expression in up.args)
            ):
                result.bare.append((node.lineno, function_of(node)))
                result.links.append((node.lineno, "/"))
            else:
                result.unfollowed.append((node.lineno, function_of(node)))
            break
    result.links.sort()
    return result


_COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_GET_DECLARED = re.compile(r"export\s+(?:async\s+)?function\s+GET\b|export\s+(?:const|let|var)\s+GET\b")
_EXPORT_LIST = re.compile(r"export\s*\{([^}]*)\}")


def _exports_get(text: str) -> bool:
    code = _COMMENTS.sub("", text)
    if _GET_DECLARED.search(code):
        return True
    return any(
        entry.split(" as ")[-1].strip() == "GET"
        for listed in _EXPORT_LIST.findall(code)
        for entry in listed.split(",")
        if entry.strip()
    )


def _route_dirs(base: Path, segments: list[str]) -> list[Path]:
    """The directories under ``base`` that a path's segments reach."""
    reached: list[Path] = []
    children = sorted(child for child in base.iterdir() if child.is_dir())
    for child in children:
        if child.name.startswith("(") and child.name.endswith(")"):
            reached += _route_dirs(child, segments)
    if not segments:
        return [base, *reached, *(child for child in children if child.name.startswith("[[..."))]
    head, rest = segments[0], segments[1:]
    for child in children:
        name = child.name
        if name.startswith(("_", "(", "@")):
            continue
        if name.startswith(("[...", "[[...")):
            reached.append(child)
        elif name.startswith("[") and name.endswith("]"):
            reached += _route_dirs(child, rest)
        elif name == head:
            reached += _route_dirs(child, rest)
    return reached


def _serves(directory: Path) -> bool:
    if any((directory / name).is_file() for name in PAGE_FILES):
        return True
    return any((directory / name).is_file() and _exports_get((directory / name).read_text(encoding="utf-8")) for name in ROUTE_FILES)


def resolves(path: str, app: Path = FRONTEND_APP, public: Path = FRONTEND_PUBLIC) -> bool:
    """True if the frontend serves ``path``: a page, a route handler for GET, or a public file."""
    if not path.startswith("/"):
        return False
    segments = [segment for segment in path.split("/") if segment]
    if segments and SPLICE not in path and public.joinpath(*segments).is_file():
        return True
    return any(_serves(directory) for directory in _route_dirs(app, segments))


def _shown(path: str) -> str:
    return path.replace(SPLICE, "{…}")


def test_every_frontend_url_read_in_the_backend_is_a_link_to_a_page_the_frontend_serves():
    links, unfollowed, bare = [], [], Counter()
    for path in sorted(BACKEND_APP.rglob("*.py")):
        module = str(path.relative_to(ROOT))
        scanned = scan_module(path.read_text(encoding="utf-8"), module)
        links += [(f"{module}:{line}", link) for line, link in scanned.links]
        unfollowed += [f"{module}:{line} (in {function})" for line, function in scanned.unfollowed]
        bare.update((module, function) for _, function in scanned.bare)
    assert not unfollowed, (
        "these FRONTEND_URL reads lead somewhere the scan cannot follow: build the link as an f-string or a + "
        "chain that starts from the origin, or, for the bare origin as the home page, list the function in "
        "BARE_ORIGINS with its count and reason:\n" + "\n".join(unfollowed)
    )
    assert dict(bare) == {where: count for where, (count, _) in BARE_ORIGINS.items()}, "the bare origins read differ from BARE_ORIGINS"
    # The scan reads the links it should: the mails', the OAuth refusals' and the invite's among them.
    assert len(links) >= 25, links
    assert {"/", "/login", "/register", "/waitlist", "/filing/" + SPLICE, "/verify-email"} <= {link for _, link in links}
    unserved = [f"{where} -> {_shown(link)}" for where, link in links if not resolves(link)]
    assert not unserved, (
        "these links lead to no page, GET route handler or public file under frontend/; give the path a page "
        "or change the link:\n" + "\n".join(unserved)
    )


PLANTED = '''
from urllib.parse import urljoin

from app.config import settings
from app.services.elsewhere import IMPORTED_PATH, IMPORTED_BASE

TILE = "/assets/earningsnerd-appicon.png"
ANNOTATED: str = "/nowhere-annotated"
CONSTANT = "/nowhere-constant"
ROUTE = "/login"
ROUTE = ROUTE.replace("login", "nowhere")
_BASE = settings.FRONTEND_URL.rstrip("/")
_EXPORTED = settings.FRONTEND_URL
base_global = None
SETTINGS_LINE = f'Manage alerts in your <a href="{settings.FRONTEND_URL}/dashboard/settings" '

def removed_verification_link(token):
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/api/waitlist/verify/{token}"

def refusal():
    frontend_url = settings.FRONTEND_URL
    return f"{frontend_url}/login?error=denied"

def concatenated():
    return settings.FRONTEND_URL.rstrip("/") + "/admin/feedback"

def chained(filing_id):
    return settings.FRONTEND_URL + "/filing/" + str(filing_id)

def spliced(filing_id, ticker):
    return [f"{settings.FRONTEND_URL}/filing/{filing_id}", f"{settings.FRONTEND_URL}/company/{ticker}#news"]

def tile():
    return f"{settings.FRONTEND_URL.rstrip('/')}{TILE}"

def annotated():
    return f"{settings.FRONTEND_URL}{ANNOTATED}"

def constant_added():
    return settings.FRONTEND_URL + CONSTANT

def reassigned_constant():
    return f"{settings.FRONTEND_URL}{ROUTE}"

def imported():
    return f"{settings.FRONTEND_URL}{IMPORTED_PATH}"

def variable_added(path):
    return settings.FRONTEND_URL + path

def shadowed(TILE):
    return f"{settings.FRONTEND_URL}{TILE}"

def lone_wrapper(path):
    return f"{settings.FRONTEND_URL}".rstrip("/") + path

def nested_wrapper(path):
    return f"{f'{settings.FRONTEND_URL}'}{path}"

def home():
    return f'<a href="{settings.FRONTEND_URL}">{settings.FRONTEND_URL}</a>'

def nowhere():
    return f'<a href="{settings.FRONTEND_URL}/nowhere">'

def module_alias():
    return f"{_BASE}/pricing"

def comprehended(rows):
    names = [_BASE for _BASE in rows]
    return f"{_BASE}/pricing?names={names}"

def defaulted(_BASE=f"{_BASE}/nowhere-default"):
    return _BASE

def closure():
    base = settings.FRONTEND_URL
    def inner():
        return f"{base}/search"
    return inner

make_calendar = lambda: f"{settings.FRONTEND_URL}/calendar"

def annotated_alias():
    base: str = settings.FRONTEND_URL
    return f"{base}/contact"

def formatted():
    return "{}/x".format(settings.FRONTEND_URL)

def percent():
    return "%s/x" % settings.FRONTEND_URL

def joined():
    return "/".join([settings.FRONTEND_URL, "x"])

def url_joined():
    return urljoin(settings.FRONTEND_URL, "/x")

def handed_on():
    base = settings.FRONTEND_URL
    return build_link(base, "/x")

def lone_redirect():
    return RedirectResponse(url=f"{settings.FRONTEND_URL}")

def walrus():
    return RedirectResponse(url=(walrus_base := settings.FRONTEND_URL))

def set_global():
    global base_global
    base_global = settings.FRONTEND_URL

def via_global():
    return f"{base_global}/nowhere-global"

def augmented():
    base = settings.FRONTEND_URL
    base += "/nowhere"
    return f"{base}/x"

def reassigned():
    base = settings.FRONTEND_URL
    base = "https://www.sec.gov"
    return f"{base}/cgi-bin/browse-edgar"

class Holder:
    holder_base = settings.FRONTEND_URL

class Shadow:
    _BASE = settings.FRONTEND_URL

def another_origin():
    base = "https://www.sec.gov"
    return f"{base}/cgi-bin/browse-edgar?action=getcompany"

def imported_alias():
    return f"{IMPORTED_BASE}/api/nowhere"
'''

# The module PLANTED imports IMPORTED_BASE from: it defines the alias and reads it, so it passes here.
ELSEWHERE = '''
from app.config import settings

IMPORTED_BASE = settings.FRONTEND_URL.rstrip("/")

def local():
    return f"{IMPORTED_BASE}/pricing"
'''


def test_the_scan_follows_each_form_and_fails_closed():
    scanned = scan_module(PLANTED, "planted.py")
    lines = PLANTED.splitlines()

    def at(line: int) -> str:
        return lines[line - 1].strip()

    links = sorted((at(line), _shown(link)) for line, link in scanned.links)
    assert links == sorted([
        ('SETTINGS_LINE = f\'Manage alerts in your <a href="{settings.FRONTEND_URL}/dashboard/settings" \'', "/dashboard/settings"),
        ('return f"{base}/api/waitlist/verify/{token}"', "/api/waitlist/verify/{…}"),
        ('return f"{frontend_url}/login?error=denied"', "/login"),
        ('return settings.FRONTEND_URL.rstrip("/") + "/admin/feedback"', "/admin/feedback"),
        ('return settings.FRONTEND_URL + "/filing/" + str(filing_id)', "/filing/{…}"),
        ('return [f"{settings.FRONTEND_URL}/filing/{filing_id}", f"{settings.FRONTEND_URL}/company/{ticker}#news"]', "/filing/{…}"),
        ('return [f"{settings.FRONTEND_URL}/filing/{filing_id}", f"{settings.FRONTEND_URL}/company/{ticker}#news"]', "/company/{…}"),
        ("return f\"{settings.FRONTEND_URL.rstrip('/')}{TILE}\"", "/assets/earningsnerd-appicon.png"),
        ('return f"{settings.FRONTEND_URL}{ANNOTATED}"', "/nowhere-annotated"),
        ("return settings.FRONTEND_URL + CONSTANT", "/nowhere-constant"),
        ('return f"{settings.FRONTEND_URL}{ROUTE}"', "{…}"),
        ('return f"{settings.FRONTEND_URL}{IMPORTED_PATH}"', "{…}"),
        ("return settings.FRONTEND_URL + path", "{…}"),
        ('return f"{settings.FRONTEND_URL}{TILE}"', "{…}"),
        ('return f"{settings.FRONTEND_URL}".rstrip("/") + path', "{…}"),
        ("return f\"{f'{settings.FRONTEND_URL}'}{path}\"", "{…}"),
        ("return f'<a href=\"{settings.FRONTEND_URL}\">{settings.FRONTEND_URL}</a>'", "/"),
        ("return f'<a href=\"{settings.FRONTEND_URL}\">{settings.FRONTEND_URL}</a>'", "/"),
        ("return f'<a href=\"{settings.FRONTEND_URL}/nowhere\">'", "/nowhere"),
        ('return f"{_BASE}/pricing"', "/pricing"),
        ('return f"{_BASE}/pricing?names={names}"', "/pricing"),
        ('def defaulted(_BASE=f"{_BASE}/nowhere-default"):', "/nowhere-default"),
        ('return f"{base}/search"', "/search"),
        ('make_calendar = lambda: f"{settings.FRONTEND_URL}/calendar"', "/calendar"),
        ('return f"{base}/contact"', "/contact"),
    ])
    assert sorted({_shown(link) for _, link in scanned.links if not resolves(link)}) == sorted([
        "/api/waitlist/verify/{…}", "/nowhere", "/nowhere-annotated", "/nowhere-constant", "/nowhere-default", "{…}",
    ])
    # Each read the scan cannot follow fails as unfollowed.
    assert sorted(at(line) for line, _ in scanned.unfollowed) == sorted([
        "_EXPORTED = settings.FRONTEND_URL",  # a module's alias the module never reads
        'return "{}/x".format(settings.FRONTEND_URL)',
        'return "%s/x" % settings.FRONTEND_URL',
        'return "/".join([settings.FRONTEND_URL, "x"])',
        'return urljoin(settings.FRONTEND_URL, "/x")',
        'return build_link(base, "/x")',
        'return RedirectResponse(url=f"{settings.FRONTEND_URL}")',
        "return RedirectResponse(url=(walrus_base := settings.FRONTEND_URL))",
        'return f"{base_global}/nowhere-global"',  # a global alias the module also binds to None
        'return f"{base}/x"',  # an alias augmented in its function
        'return f"{base}/cgi-bin/browse-edgar"',  # an alias reassigned to another origin
        "holder_base = settings.FRONTEND_URL",  # a class attribute
        "_BASE = settings.FRONTEND_URL",  # a class attribute named as a module's alias
    ])
    # Planted gap: an alias another module defines and reads is followed there, not where it is imported.
    assert not any("IMPORTED_BASE" in at(line) for line, _ in scanned.links + scanned.unfollowed)
    elsewhere = scan_module(ELSEWHERE, "elsewhere.py")
    assert (elsewhere.links, elsewhere.unfollowed) == ([(7, "/pricing")], [])


def test_a_bare_origin_is_the_home_page_only_where_it_is_listed_and_as_often():
    source = '''
from urllib.parse import urljoin

from app.config import settings

def google_callback():
    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(url=frontend_url)

def apple_callback():
    frontend_url = settings.FRONTEND_URL
    detour = urljoin(frontend_url, "/nowhere")
    return _apple_redirect(frontend_url)

def elsewhere():
    return RedirectResponse(url=settings.FRONTEND_URL)
'''
    scanned = scan_module(source, "backend/app/routers/auth.py")
    assert Counter(function for _, function in scanned.bare) == {"google_callback": 1, "apple_callback": 2}
    assert [function for _, function in scanned.unfollowed] == ["elsewhere"]
    # A listed function that reads the bare origin more often than listed fails the main test's count.
    assert Counter(function for _, function in scanned.bare)["apple_callback"] != BARE_ORIGINS[("backend/app/routers/auth.py", "apple_callback")][0]


def test_the_resolver_reads_the_routes_next_serves(tmp_path):
    app, public = tmp_path / "app", tmp_path / "public"
    files = {
        "app/page.tsx": "",
        "app/(marketing)/about/page.tsx": "",
        "app/@modal/sign-in/page.tsx": "",
        "app/_lib/page.tsx": "",
        "app/docs/[[...slug]]/page.tsx": "",
        "app/files/[...rest]/page.tsx": "",
        "app/filing/[id]/page.tsx": "",
        "app/api/verify/[token]/route.ts": "export async function POST() {}",
        "app/api/commented/route.ts": "// export async function GET() {}\nexport async function POST() {}",
        "app/api/renamed/route.ts": "function GET() {}\nexport { GET as other }",
        "app/api/ok/route.ts": "export async function GET() {}",
        "app/api/aliased/route.ts": "const handler = () => null\nexport { handler as GET }",
        "public/assets/tile.png": "",
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)

    def served(path: str) -> bool:
        return resolves(path, app, public)

    assert [served(path) for path in (
        "/", "/about", "/docs", "/docs/a/b", "/files/x/y", "/filing/" + SPLICE, "/filing/123", "/api/ok",
        "/api/aliased", "/assets/tile.png",
    )] == [True] * 10
    assert [served(path) for path in (
        "/sign-in", "/_lib", "/files", "/api/verify/" + SPLICE, "/api/commented", "/api/renamed", "/marketing/about",
        "/assets/" + SPLICE, SPLICE, "/nowhere",
    )] == [False] * 10
