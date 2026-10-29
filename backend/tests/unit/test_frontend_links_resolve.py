"""Every link the backend builds on ``FRONTEND_URL`` leads to something the frontend serves.

E46 (2): the waitlist's welcome mail asked its reader to verify through
``{FRONTEND_URL}/api/waitlist/verify/{token}``, a path no frontend route served (a GET answered 404 on
www), so the step it asked for could not be taken. This reads every f-string and every ``+`` in
``backend/app`` that starts from ``FRONTEND_URL`` (``settings.FRONTEND_URL``, the same with
``.rstrip("/")``, or a name its own function assigns from one of those), takes the path after it, and
resolves that path against ``frontend/app`` (a directory holding a ``page`` or ``route`` file, where a
spliced segment takes a ``[param]`` directory and a route group ``(name)`` is passed through) or
``frontend/public`` (a file). The query and fragment are left out, a link whose text after the origin
does not start with ``/`` is the home page, and a module constant spliced in is read as its value.

Not read: a path the frontend's middleware or ``next.config.js`` would serve without a page (it has none
today: the config sets headers only), and a link built in a helper that takes the origin as an argument.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_APP = ROOT / "backend" / "app"
FRONTEND_APP = ROOT / "frontend" / "app"
FRONTEND_PUBLIC = ROOT / "frontend" / "public"
ROUTE_FILES = ("page.tsx", "page.ts", "page.jsx", "page.js", "route.ts", "route.tsx", "route.js")
# A value the code splices into a path: it can stand only where a [param] directory does.
SPLICE = "\x00"
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _reads_origin(node: ast.AST, aliases: set[str]) -> bool:
    """``settings.FRONTEND_URL``, the same stripped of its slash, or a name assigned from one of those."""
    if isinstance(node, ast.Name):
        return node.id in aliases
    if isinstance(node, ast.Attribute):
        return node.attr == "FRONTEND_URL"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("rstrip", "strip"):
        return _reads_origin(node.func.value, aliases)
    return False


def _own_nodes(scope: ast.AST):
    """The nodes of ``scope`` outside the functions and classes it defines, those nodes included."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _SCOPES):
            stack.extend(ast.iter_child_nodes(node))


def _path(parts: list[ast.expr], constants: dict[str, str]) -> str:
    text = "".join(
        part.value if isinstance(part, ast.Constant) and isinstance(part.value, str)
        else constants.get(part.value.id, SPLICE)
        if isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name)
        else SPLICE
        for part in parts
    )
    if not text.startswith("/"):
        return "/"
    return re.split(r"[?#\"'\s<>]", text, maxsplit=1)[0]


def _link_path(node: ast.AST, aliases: set[str], constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.JoinedStr):
        for at, part in enumerate(node.values):
            if isinstance(part, ast.FormattedValue) and _reads_origin(part.value, aliases):
                return _path(node.values[at + 1:], constants)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and _reads_origin(node.left, aliases):
        if isinstance(node.right, ast.JoinedStr):
            return _path(node.right.values, constants)
        return _path([node.right], constants)
    return None


def frontend_links(source: str) -> list[tuple[int, str]]:
    """Each link ``source`` builds on the frontend's origin, as (line, path)."""
    tree = ast.parse(source)
    constants = {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    found: list[tuple[int, str]] = []

    def scan(scope: ast.AST) -> None:
        nodes = list(_own_nodes(scope))
        aliases = {
            target.id
            for node in nodes
            if isinstance(node, ast.Assign) and _reads_origin(node.value, set())
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for node in nodes:
            path = _link_path(node, aliases, constants)
            if path is not None:
                found.append((node.lineno, path))
            if isinstance(node, _SCOPES):
                scan(node)

    scan(tree)
    return sorted(found)


def _route_dirs(base: Path, segments: list[str]) -> list[Path]:
    """The directories under ``base`` that a path's segments reach."""
    reached: list[Path] = []
    children = sorted(child for child in base.iterdir() if child.is_dir())
    for child in children:
        if child.name.startswith("(") and child.name.endswith(")"):
            reached += _route_dirs(child, segments)
    if not segments:
        return [base, *reached]
    head, rest = segments[0], segments[1:]
    for child in children:
        name = child.name
        if name.startswith(("[...", "[[...")):
            reached.append(child)
        elif name.startswith("[") and name.endswith("]"):
            reached += _route_dirs(child, rest)
        elif name == head:
            reached += _route_dirs(child, rest)
    return reached


def resolves(path: str) -> bool:
    """True if the frontend serves ``path``: a page or route handler, or a public file."""
    segments = [segment for segment in path.split("/") if segment]
    if segments and SPLICE not in path and FRONTEND_PUBLIC.joinpath(*segments).is_file():
        return True
    return any((directory / name).is_file() for directory in _route_dirs(FRONTEND_APP, segments) for name in ROUTE_FILES)


def test_every_link_the_backend_builds_on_the_frontend_origin_reaches_a_page_it_serves():
    links = [
        (f"{path.relative_to(ROOT)}:{line}", link)
        for path in sorted(BACKEND_APP.rglob("*.py"))
        for line, link in frontend_links(path.read_text(encoding="utf-8"))
    ]
    # The scan reads the links it should: the mails', the OAuth refusals' and the invite's among them.
    assert len(links) >= 20, links
    assert {"/login", "/register", "/waitlist", "/filing/" + SPLICE, "/verify-email"} <= {link for _, link in links}
    unserved = [f"{where} -> {link.replace(SPLICE, '{…}')}" for where, link in links if not resolves(link)]
    assert not unserved, (
        "these links lead to no page, route handler or public file under frontend/; give the path a page or "
        "change the link:\n" + "\n".join(unserved)
    )


def test_the_scan_reads_each_form_a_link_takes_and_fails_one_that_leads_nowhere():
    planted = '''
from app.config import settings

TILE = "/assets/earningsnerd-appicon.png"
SETTINGS_LINE = f'Manage alerts in your <a href="{settings.FRONTEND_URL}/dashboard/settings" '

def removed_verification_link(token):
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/api/waitlist/verify/{token}"

def refusal():
    frontend_url = settings.FRONTEND_URL
    return f"{frontend_url}/login?error=denied"

def concatenated():
    return settings.FRONTEND_URL.rstrip("/") + "/admin/feedback"

def spliced(filing_id, ticker):
    return [f"{settings.FRONTEND_URL}/filing/{filing_id}", f"{settings.FRONTEND_URL}/company/{ticker}#news"]

def tile():
    return f"{settings.FRONTEND_URL.rstrip('/')}{TILE}"

def home():
    return f'<a href="{settings.FRONTEND_URL}">{settings.FRONTEND_URL}</a>'

def nowhere():
    return f'<a href="{settings.FRONTEND_URL}/nowhere">'

def another_origin():
    base = "https://www.sec.gov"
    return f"{base}/cgi-bin/browse-edgar"
'''
    links = [link for _, link in frontend_links(planted)]
    assert links == [
        "/dashboard/settings",
        "/api/waitlist/verify/" + SPLICE,
        "/login",
        "/admin/feedback",
        "/company/" + SPLICE,
        "/filing/" + SPLICE,
        "/assets/earningsnerd-appicon.png",
        "/",
        "/nowhere",
    ]
    assert [link for link in links if not resolves(link)] == ["/api/waitlist/verify/" + SPLICE, "/nowhere"]

