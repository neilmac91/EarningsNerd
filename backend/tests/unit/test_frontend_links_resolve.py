"""Every link the backend builds on ``FRONTEND_URL`` leads to something the frontend serves.

E46 (2): the waitlist's welcome mail asked its reader to verify through
``{FRONTEND_URL}/api/waitlist/verify/{token}``, a path no frontend route served (a GET answered 404 on
www), so the step it asked for could not be taken.

The scan reads every ``FRONTEND_URL`` read in ``backend/app`` and fails closed: each must be followed to
a link, or the gate fails. A read is ``<anything>.FRONTEND_URL``, the same through ``.rstrip(...)`` or
``.strip(...)``, or a name assigned from one of those (an alias), resolved by Python's scope rules: an
alias of the module is seen in its functions, and one of a function in the functions and lambdas inside
it, unless a scope binds the name itself. A read is followed when it is:

- a replacement field of an f-string: the link's path is the text after it;
- the left end of a ``+`` chain: the path is the chain's other operands, joined;
- the value an alias is assigned, in a module or a function: the alias's reads are followed in turn;
- a bare origin listed in ``BARE_ORIGINS`` by module and function, with its reason: the home page.

A path runs to the first ``? # " ' < >`` or space, and an empty one is the home page. A spliced value
stands for a segment and takes only a ``[param]`` directory; a module constant spliced in, assigned or
annotated, is read as its value unless the scope binds the name. A path that does not start with ``/``
once read (a spliced value first, an imported name) fails as unreadable. The path resolves against
``frontend/app``: a directory holding a ``page`` file, or a ``route`` file that exports ``GET``, where a
route group ``(name)`` and a parallel-route slot ``@name`` add no segment, a ``_private`` folder is never
routed, a catch-all takes the rest and an optional one also none. Or it resolves against
``frontend/public``: a file.

Not read, and planted as gaps in ``test_the_scan_follows_each_form_and_fails_closed``: an alias imported
from another module (the link is not read, and the read that made the alias passes as an alias); and an
alias reassigned to another origin in its own function (aliases are read by name, not by flow, so the
other origin's path is checked here and fails). Not read at all: the origin taken by ``getattr`` with
the setting's name as a string. Not served, so a link to one fails: Next's metadata
routes (``sitemap.ts`` as ``/sitemap.xml``, ``robots.ts``, ``manifest.ts``, ``opengraph-image``,
``icon``), and a path that ``middleware.ts`` or ``next.config.js`` would serve without a page (the config
sets headers only).
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_APP = ROOT / "backend" / "app"
FRONTEND_APP = ROOT / "frontend" / "app"
FRONTEND_PUBLIC = ROOT / "frontend" / "public"
PAGE_FILES = ("page.tsx", "page.ts", "page.jsx", "page.js", "page.mdx")
ROUTE_FILES = ("route.ts", "route.tsx", "route.js")
_GET_EXPORT = re.compile(r"export\s+(?:async\s+)?function\s+GET\b|export\s+const\s+GET\b|export\s*\{[^}]*\bGET\b[^}]*\}")
# A value the code splices into a path: it stands only where a [param] directory does.
SPLICE = "\x00"
_URL_END = re.compile(r"[?#\"'<>\s]")
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_STRIPS = ("rstrip", "strip")

# A bare origin read is a link to the home page only where it is listed: (module, function) and why.
BARE_ORIGINS = {
    ("backend/app/routers/auth.py", "google_callback"): "a reader Google signs in lands on the home page",
    ("backend/app/routers/auth.py", "apple_callback"): "a reader Apple signs in lands on the home page",
    ("backend/app/services/email_service.py", "_filing_url"): "an alert with no filing page of ours links the home page",
}


@dataclass
class _Scope:
    node: ast.AST
    parent: _Scope | None
    bound: set[str] = field(default_factory=set)
    aliases: set[str] = field(default_factory=set)


@dataclass
class Scan:
    links: list[tuple[int, str]] = field(default_factory=list)  # (line of the read, path)
    unfollowed: list[tuple[int, str]] = field(default_factory=list)  # (line, enclosing function)
    bare: list[tuple[int, str]] = field(default_factory=list)  # (line, enclosing function)


def _own_nodes(scope: ast.AST):
    """The nodes of ``scope``, not descending into the functions and classes it defines."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (*_FUNCTIONS, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(node))


def _bound(scope: ast.AST) -> set[str]:
    """The names ``scope`` binds itself: its parameters, assignments, imports and definitions."""
    names: set[str] = set()
    if isinstance(scope, _FUNCTIONS):
        args = scope.args
        names |= {arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg) if arg}
    declared_elsewhere: set[str] = set()
    for node in _own_nodes(scope):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            declared_elsewhere |= set(node.names)
    return names - declared_elsewhere


def _innermost(name: str, scope: _Scope | None) -> _Scope | None:
    """The scope a name read in ``scope`` resolves to (class bodies are not on the chain)."""
    while scope is not None:
        if name in scope.bound:
            return scope
        scope = scope.parent
    return None


def _is_alias(node: ast.Name, scope: _Scope) -> bool:
    owner = _innermost(node.id, scope)
    return owner is not None and node.id in owner.aliases


def _origin(node: ast.AST, scope: _Scope) -> bool:
    """True if ``node`` is the frontend's origin: a read of it, stripped or not, or an alias of it."""
    if isinstance(node, ast.Attribute):
        return node.attr == "FRONTEND_URL" and isinstance(node.ctx, ast.Load)
    if isinstance(node, ast.Name):
        return isinstance(node.ctx, ast.Load) and _is_alias(node, scope)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _STRIPS:
        return _origin(node.func.value, scope)
    return False


def _alias_targets(node: ast.AST) -> list[str] | None:
    """The names an assignment binds, if it binds only names; None for any other target."""
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
        targets = [node.target]
    else:
        return None
    return [target.id for target in targets] if all(isinstance(target, ast.Name) for target in targets) else None


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
    path = _URL_END.split(text, maxsplit=1)[0]
    return path or "/"


def scan_module(source: str, module: str) -> Scan:
    """Follow every read of the frontend's origin in ``source``, the module at ``module``."""
    if "FRONTEND_URL" not in source:
        return Scan()  # it reads none: an alias imported from elsewhere is the planted gap
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for name in _alias_targets(node) or []:
                constants[name] = node.value.value

    scopes: dict[ast.AST, _Scope] = {}

    def build(node: ast.AST, parent: _Scope | None) -> None:
        scope = _Scope(node, parent, _bound(node))
        scopes[node] = scope
        own = list(_own_nodes(node))
        grown = True
        while grown:  # an alias may be assigned from another alias
            grown = False
            for statement in own:
                names = _alias_targets(statement)
                if names and statement.value is not None and _origin(statement.value, scope):
                    if not set(names) <= scope.aliases:
                        scope.aliases |= set(names)
                        grown = True
        for inner in own:
            if isinstance(inner, _FUNCTIONS):
                build(inner, scope)
            elif isinstance(inner, ast.ClassDef):
                build_class(inner, scope)

    def build_class(node: ast.ClassDef, enclosing: _Scope) -> None:
        # A class body's names are not seen by its methods: its statements resolve through ``enclosing``.
        scopes[node] = enclosing
        for inner in _own_nodes(node):
            if isinstance(inner, _FUNCTIONS):
                build(inner, enclosing)
            elif isinstance(inner, ast.ClassDef):
                build_class(inner, enclosing)

    build(tree, None)

    def scope_of(node: ast.AST) -> _Scope:
        up = parents.get(node)
        while up is not None and up not in scopes:
            up = parents.get(up)
        return scopes[up if up is not None else tree]

    def function_of(node: ast.AST) -> str:
        up = parents.get(node)
        while up is not None and not isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef)):
            up = parents.get(up)
        return up.name if up is not None else "<module>"

    result = Scan()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if not _origin(node, scope_of(node)):
                continue
        elif not (isinstance(node, ast.Name) and _origin(node, scope_of(node))):
            continue
        scope = scope_of(node)
        # The expression the read stands in: through a strip of it, if any.
        expression = node
        while True:
            up = parents.get(expression)
            if isinstance(up, ast.Attribute) and up.attr in _STRIPS and isinstance(parents.get(up), ast.Call) and parents[up].func is up:
                expression = parents[up]
            else:
                break
        up = parents.get(expression)
        if isinstance(up, ast.FormattedValue) and isinstance(parents.get(up), ast.JoinedStr):
            values = parents[up].values
            result.links.append((node.lineno, _path(values[values.index(up) + 1:], scope, constants)))
        elif isinstance(up, ast.BinOp) and isinstance(up.op, ast.Add) and up.left is expression:
            rest: list[ast.AST] = []
            chain = up
            while isinstance(chain, ast.BinOp) and isinstance(chain.op, ast.Add):
                rest.append(chain.right)
                parent = parents.get(chain)
                if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add) and parent.left is chain:
                    chain = parent
                else:
                    break
            result.links.append((node.lineno, _path(rest, scope, constants)))
        elif (names := _alias_targets(up)) and up.value is expression and set(names) <= scope.aliases:
            pass  # an alias's definition, in a module or a function: its reads are followed where they stand
        elif (module, function_of(node)) in BARE_ORIGINS:
            result.bare.append((node.lineno, function_of(node)))
            result.links.append((node.lineno, "/"))
        else:
            result.unfollowed.append((node.lineno, function_of(node)))
    result.links.sort()
    return result


def _route_dirs(base: Path, segments: list[str]) -> list[Path]:
    """The directories under ``base`` that a path's segments reach."""
    reached: list[Path] = []
    children = sorted(child for child in base.iterdir() if child.is_dir())
    for child in children:
        if (child.name.startswith("(") and child.name.endswith(")")) or child.name.startswith("@"):
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
    return any(
        (directory / name).is_file() and _GET_EXPORT.search((directory / name).read_text(encoding="utf-8"))
        for name in ROUTE_FILES
    )


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
    links, unfollowed, bare_used = [], [], set()
    for path in sorted(BACKEND_APP.rglob("*.py")):
        module = str(path.relative_to(ROOT))
        scanned = scan_module(path.read_text(encoding="utf-8"), module)
        links += [(f"{module}:{line}", link) for line, link in scanned.links]
        unfollowed += [f"{module}:{line} (in {function})" for line, function in scanned.unfollowed]
        bare_used |= {(module, function) for _, function in scanned.bare}
    assert not unfollowed, (
        "these FRONTEND_URL reads lead somewhere the scan cannot follow: build the link as an f-string or a + "
        "chain that starts from the origin, or, for the bare origin as the home page, list the function in "
        "BARE_ORIGINS with its reason:\n" + "\n".join(unfollowed)
    )
    assert bare_used == set(BARE_ORIGINS), f"BARE_ORIGINS lists functions that read no bare origin: {set(BARE_ORIGINS) - bare_used}"
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
_BASE = settings.FRONTEND_URL.rstrip("/")
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

def imported():
    return f"{settings.FRONTEND_URL}{IMPORTED_PATH}"

def variable_added(path):
    return settings.FRONTEND_URL + path

def shadowed(TILE):
    return f"{settings.FRONTEND_URL}{TILE}"

def home():
    return f'<a href="{settings.FRONTEND_URL}">{settings.FRONTEND_URL}</a>'

def nowhere():
    return f'<a href="{settings.FRONTEND_URL}/nowhere">'

def module_alias():
    return f"{_BASE}/pricing"

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

class Holder:
    base = settings.FRONTEND_URL

def another_origin():
    base = "https://www.sec.gov"
    return f"{base}/cgi-bin/browse-edgar?action=getcompany"

def imported_alias():
    return f"{IMPORTED_BASE}/api/nowhere"

def reassigned(token):
    base = settings.FRONTEND_URL
    base = "https://www.sec.gov"
    return f"{base}/cgi-bin/browse-edgar"
'''


def test_the_scan_follows_each_form_and_fails_closed():
    scanned = scan_module(PLANTED, "planted.py")
    lines = PLANTED.splitlines()

    def at(line: int) -> str:
        return lines[line - 1].strip()

    links = {(at(line), _shown(link)) for line, link in scanned.links}
    assert links == {
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
        ('return f"{settings.FRONTEND_URL}{IMPORTED_PATH}"', "{…}"),
        ("return settings.FRONTEND_URL + path", "{…}"),
        ('return f"{settings.FRONTEND_URL}{TILE}"', "{…}"),
        ("return f'<a href=\"{settings.FRONTEND_URL}\">{settings.FRONTEND_URL}</a>'", "/"),
        ("return f'<a href=\"{settings.FRONTEND_URL}/nowhere\">'", "/nowhere"),
        ('return f"{_BASE}/pricing"', "/pricing"),
        ('return f"{base}/search"', "/search"),
        ('make_calendar = lambda: f"{settings.FRONTEND_URL}/calendar"', "/calendar"),
        ('return f"{base}/contact"', "/contact"),
        # Planted gap: the alias is read by name, not by flow, so the other origin's path is checked and fails.
        ('return f"{base}/cgi-bin/browse-edgar"', "/cgi-bin/browse-edgar"),
    }
    refused = {(link, served) for link, served in ((link, resolves(link)) for _, link in scanned.links) if not served}
    assert {_shown(link) for link, _ in refused} == {
        "/api/waitlist/verify/{…}", "/nowhere", "/nowhere-annotated", "/nowhere-constant", "{…}", "/cgi-bin/browse-edgar",
    }
    # Each read the scan cannot follow fails as unfollowed, the class attribute's among them.
    assert sorted(at(line) for line, _ in scanned.unfollowed) == sorted([
        'return "{}/x".format(settings.FRONTEND_URL)',
        'return "%s/x" % settings.FRONTEND_URL',
        'return "/".join([settings.FRONTEND_URL, "x"])',
        'return urljoin(settings.FRONTEND_URL, "/x")',
        'return build_link(base, "/x")',
        "base = settings.FRONTEND_URL",
    ])
    assert [function for _, function in scanned.unfollowed if function == "<module>"] == ["<module>"]
    # Planted gap: an alias imported from another module is not a read here, so its link is not read.
    assert not any("IMPORTED_BASE" in at(line) for line, _ in scanned.links + scanned.unfollowed)


def test_a_bare_origin_is_the_home_page_only_where_it_is_listed():
    source = '''
from app.config import settings

def google_callback():
    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(url=frontend_url)

def elsewhere():
    return RedirectResponse(url=settings.FRONTEND_URL)
'''
    scanned = scan_module(source, "backend/app/routers/auth.py")
    assert [(link, function) for (_, link), (_, function) in zip(scanned.links, scanned.bare)] == [("/", "google_callback")]
    assert [function for _, function in scanned.unfollowed] == ["elsewhere"]


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
        "/", "/about", "/sign-in", "/docs", "/docs/a/b", "/files/x/y", "/filing/" + SPLICE, "/filing/123",
        "/api/ok", "/api/aliased", "/assets/tile.png",
    )] == [True] * 11
    assert [served(path) for path in (
        "/_lib", "/files", "/api/verify/" + SPLICE, "/marketing/about", "/assets/" + SPLICE, SPLICE, "/nowhere",
    )] == [False] * 7
