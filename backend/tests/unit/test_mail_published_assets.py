"""Gate: mail addresses a file of the site's only by a registered path, built on FRONTEND_URL.

Sent mail keeps every address it carries for as long as the message is kept, and nobody can edit it
after sending, so a file of the site's that the backend puts in mail is published: its path must never
move or change (``frontend/public/assets/LOGO_README.md`` › Published URLs stay put). The register,
``frontend/tests/unit/publishedAssetUrls.json``, names the published paths and the origin mail
addresses them on, and ``frontend/tests/unit/publishedAssetUrls.spec.ts`` holds each path to its
file's bytes and keeps the middleware and every redirect and rewrite off it. This gate holds the
backend to the rule's mail half (CLAUDE.md rule 12). It reads every file in ``backend/app``: the
Python's strings as the code builds them (an f-string or a ``+`` chain whole, a name bound to a
registered path read as the path), docstrings and the API's route decorators aside, and every other
file's text. In them:

- the path of a file the site serves from ``frontend/public``, or of one of its directories, where a
  URL path can start (the start of a string, after whitespace, a quote or a backtick, a bracket, "=",
  ":", ",", ";", or a placeholder such as ``{base}``, ``%s``, ``$base``, ``__BASE__`` or a host the code
  fills in, ``https://{host}``) spells a whole registered path, and nothing is filled in after it. A
  directory left open for a name to follow (``"/assets/"``, ``f"{base}/icons/{name}"``) fails, so a
  path composed at run time has to be written out whole;
- no origin of the site's (``earningsnerd.io`` or any host under it, with or without a scheme), no
  second slash and no ``FRONTEND_URL`` that keeps its trailing slash comes in front of such a path:
  mail builds it on ``FRONTEND_URL`` with the slash stripped, and a doubled slash answers 308;
- a registered path is used whole. Its string may sit in the f-string or the concatenation that
  builds an address, in a template a ``.format``, ``%`` or ``string.Template`` fills, or in a name
  bound to it once, which is then read only in those places. Anything else
  fails, since the scan cannot follow the path into code that may change it: an argument, a
  container's item, a default, a return value, a method or a slice applied to it, a second binding.
  An address built on one may go anywhere, but no method or slice may change it.

The header's tile follows ``FRONTEND_URL`` whatever it is set to, with a trailing slash stripped, and
``FRONTEND_URL``'s default is the register's origin.

``FORMS`` plants a case for each way the rule can be broken and each look-alike that must pass.
``test_the_scan_scores_every_planted_form`` writes each case into a directory and scores it through the
walk that reads ``backend/app``. Out of reach, and planted as gaps:
- a path written with no slash before it (``"assets/x.png"`` joined to a base that ends in one);
- a registered path after a placeholder that holds an origin other than ``FRONTEND_URL``, as a
  variable or as a host filled in (the scan reads the path, not what is filled in before it);
- a path after a bare word, which reads like a file path (``BASE_URL/assets/x.png``);
- an address a function hands back, changed by its caller (the scan does not follow a value out of
  a call);
- a path the site serves from a route rather than a file (``app/manifest.ts``).

Whether the register's origin answers without a redirect is review-checked: this suite runs offline.
"""
import ast
import json
import re
from pathlib import Path

from app.config import Settings, settings
from app.services import email_service

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
APP = BACKEND / "app"
PUBLIC = REPO / "frontend" / "public"
REGISTER = json.loads((REPO / "frontend" / "tests" / "unit" / "publishedAssetUrls.json").read_text(encoding="utf-8"))
REGISTERED = frozenset(entry["url"] for entry in REGISTER["paths"])
ORIGIN = REGISTER["origin"]

# The site's own top-level names under frontend/public: its directories and the files at its root.
SITE_NAMES = sorted((p.name for p in PUBLIC.iterdir() if not p.name.startswith(".")), key=len, reverse=True)
_SITE_PATH = re.compile(r"/(?:" + "|".join(map(re.escape, SITE_NAMES)) + r")(?![A-Za-z0-9_.-])")
# What ends a URL path: whitespace, a quote, markup, a bracket, a separator, a query or a fragment, an
# entity, a placeholder or an escape. Anything else (";", "@", "+") is read into the path.
_PATH = re.compile(r"""[^\s"'`<>()\[\],?#&{}%$\\|^]*""")
_ORIGIN_BEFORE = re.compile(r"""(?:https?:)?//([^/\s"'`<>]*)/*$""", re.IGNORECASE)
_SITE_HOST_BEFORE = re.compile(r"(?:^|[^\w.-])(?:[\w-]+\.)*earningsnerd\.io(?::\d+)?/*$", re.IGNORECASE)
# A placeholder a base is put in, ending right before the path: %s, %(base)s, $base, %BASE%, @BASE@, __BASE__.
_PLACEHOLDER_BEFORE = re.compile(r"(?:%(?:\(\w+\))?[sr]|\$\w+|%\w+%|@\w+@|__\w+__)$")
_FILLED_IN_HOST = re.compile(r"[{}%$]")  # https://{host}, https://%s, https://$host
_DELIMITERS = set(" \t\r\n\"'`<>()[]=:,;}")
_LEFT_OPEN = set("{%$")  # a placeholder right after a path fills something in after it
# How the scan reads what an f-string or a concatenation holds besides its literal text: an expression
# it cannot read, and FRONTEND_URL read whole, trailing slash and all.
_FIELD = "{}"
_UNSTRIPPED = "{FRONTEND_URL}"
_ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "head", "options", "api_route", "route", "websocket"}
_FILLS = {"format", "format_map"}
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _site_host(host: str) -> bool:
    host = host.lower().rsplit("@", 1)[-1].split(":", 1)[0]
    return host == "earningsnerd.io" or host.endswith(".earningsnerd.io")


def _scan(text: str) -> tuple[list[str], set[str]]:
    """The ways ``text`` addresses a file of the site's other than by a whole registered path, and the
    registered paths it spells."""
    found: list[str] = []
    registered: set[str] = set()
    for match in _SITE_PATH.finditer(text):
        before = text[: match.start()]
        path = _PATH.match(text, match.start()).group(0)
        left_open = text[match.start() + len(path) : match.start() + len(path) + 1] in _LEFT_OPEN
        path = path.rstrip(".")  # a full stop after a path ends a sentence
        origin = _ORIGIN_BEFORE.search(before)
        if origin and not _site_host(origin.group(1)):
            if not _FILLED_IN_HOST.search(origin.group(1)):
                continue  # another site's file is not the site's to publish
            before, origin = _FIELD + before[len(before.rstrip("/")) :], None  # read the path as after a base
        if origin or _SITE_HOST_BEFORE.search(before):
            found.append(f"{(origin or _SITE_HOST_BEFORE.search(before)).group(0).lstrip()}{path}: an origin of the site's in front of the path")
            continue
        if before.endswith(_UNSTRIPPED):  # and the path after it is read, as after any base
            found.append(f"{_UNSTRIPPED}{path}: FRONTEND_URL in front of the path keeps its trailing slash: strip it")
        elif before.endswith("/"):
            found.append(f"/{path}: a doubled slash in front of the path")
            continue
        elif before and before[-1] not in _DELIMITERS and not _PLACEHOLDER_BEFORE.search(before):
            continue  # a file path or a sub-path of another URL ("app/assets/", "/static/assets/")
        if path not in REGISTERED:
            found.append(f"{path}: not a whole registered path")
        elif left_open:
            found.append(f"{path}: something is filled in after a registered path")
        else:
            registered.add(path)
    return found, registered


def _skipped(nodes: list[ast.AST]) -> set[int]:
    """The strings that are documentation (docstrings) or the API's own routes (``@router.get(...)``)."""
    ids: set[int] = set()
    for node in nodes:
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for route in node.decorator_list:
                if (
                    isinstance(route, ast.Call)
                    and isinstance(route.func, ast.Attribute)
                    and route.func.attr in _ROUTE_DECORATORS
                    and route.args
                    and isinstance(route.args[0], ast.Constant)
                ):
                    ids.add(id(route.args[0]))
    return ids


def _string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        return node.value if isinstance(node.value, str) else node.value.decode("latin-1")
    return None


def _exports(tree: ast.Module) -> dict[str, tuple[str, bool]]:
    """The names a module binds, outside any function, to a string that spells a registered path."""
    names: dict[str, tuple[str, bool]] = {}
    bodies = [tree.body]
    while bodies:
        for statement in bodies.pop():
            if isinstance(statement, ast.ClassDef):
                bodies.append(statement.body)
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target] if isinstance(statement, ast.AnnAssign) else []
            text = _string(statement.value) if targets and statement.value is not None else None
            if text is not None and _scan(text)[1] and all(isinstance(t, ast.Name) for t in targets):
                names.update((t.id, (text, True)) for t in targets)
    return names


def _scan_python(tree: ast.Module, where: str, exported: dict[str, tuple[str, bool]]) -> tuple[list[str], dict[str, set[str]]]:
    nodes: list[ast.AST] = [tree]
    parent: dict[ast.AST, ast.AST] = {}
    for node in nodes:  # one walk, breadth first, so a name is bound before a later binding reads it
        for child in ast.iter_child_nodes(node):
            parent[child] = node
            nodes.append(child)
    skip = _skipped(nodes)
    found: list[str] = []
    registered: dict[str, set[str]] = {}
    # (scope, name) -> (what the name holds, whether it is a bare path rather than an address built on
    # one, the target that binds it); a scope is the function that binds the name, or None, the module.
    names: dict[tuple[ast.AST | None, str], tuple[str, bool, ast.AST | None]] = {}
    held: set[str] = set()  # the names in ``names``, for a quick test before a scope is looked up

    def scope(node: ast.AST) -> ast.AST | None:
        node = parent.get(node)
        while node is not None and not isinstance(node, _SCOPES):
            node = parent.get(node)
        return node

    def bound(node: ast.AST) -> tuple[str, bool, ast.AST | None] | None:
        if isinstance(node, ast.Name) and node.id in held:
            here = scope(node)
            while (here, node.id) not in names and here is not None:
                here = scope(here)
            return names.get((here, node.id))
        if isinstance(node, ast.Attribute) and node.attr in exported:
            return (*exported[node.attr], None)
        return None

    def render(node: ast.AST) -> str:
        """The text an f-string or a ``+`` chain builds, a name bound to a registered path read as it."""
        if (text := _string(node)) is not None:
            return text
        if isinstance(node, ast.JoinedStr):
            return "".join(render(value) for value in node.values)
        if isinstance(node, ast.FormattedValue):
            return render(node.value) if node.conversion == -1 and node.format_spec is None else _FIELD
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return render(node.left) + render(node.right)
        if getattr(node, "attr", getattr(node, "id", None)) == "FRONTEND_URL":
            return _UNSTRIPPED
        return holds[0] if (holds := bound(node)) else _FIELD

    def rendered(node: ast.AST) -> bool:
        """Whether ``node`` is part of the f-string or the ``+`` chain around it, which is read whole."""
        up = parent.get(node)
        if isinstance(up, ast.FormattedValue):
            return up.value is node and up.conversion == -1 and up.format_spec is None and isinstance(parent.get(up), ast.JoinedStr)
        return isinstance(up, ast.JoinedStr) or (isinstance(up, ast.BinOp) and isinstance(up.op, ast.Add))

    def filled(node: ast.AST) -> bool:
        """Whether ``node`` is a template the code fills: ``s.format(...)``, ``s % ...``, ``Template(s)``."""
        up = parent.get(node)
        if isinstance(up, ast.Attribute) and up.value is node and up.attr in _FILLS:
            return isinstance(parent.get(up), ast.Call) and parent[up].func is up
        if isinstance(up, ast.BinOp) and isinstance(up.op, ast.Mod):
            return up.left is node
        callee = getattr(up, "func", None)
        return (
            isinstance(up, ast.Call)
            and getattr(callee, "attr", getattr(callee, "id", None)) == "Template"
            and bool(up.args)
            and up.args[0] is node
        )

    def changed(node: ast.AST) -> bool:
        """Whether a method other than a template's fill, an index or a slice is applied to ``node``."""
        up = parent.get(node)
        if isinstance(up, ast.Subscript):
            return up.value is node
        return isinstance(up, ast.Attribute) and up.value is node and up.attr not in _FILLS

    def binding(node: ast.AST) -> list[ast.Name] | None:
        """The names ``node`` is bound to, when it is the whole value of an assignment to names."""
        up = parent.get(node)
        targets = up.targets if isinstance(up, ast.Assign) else [up.target] if isinstance(up, ast.AnnAssign) else []
        return targets if targets and up.value is node and all(isinstance(t, ast.Name) for t in targets) else None

    def strings() -> list[ast.AST]:
        """Each string the scan reads: an f-string or a ``+`` chain whole, or a literal on its own."""
        return [
            node
            for node in nodes
            if (_string(node) is not None or isinstance(node, ast.JoinedStr) or (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)))
            and id(node) not in skip
            and not rendered(node)
        ]

    for node in nodes:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in exported:
                    names.setdefault((scope(node), alias.asname or alias.name), (*exported[alias.name], None))
                    held.add(alias.asname or alias.name)
        elif (_string(node) is not None or isinstance(node, (ast.JoinedStr, ast.BinOp))) and (targets := binding(node)):
            text = render(node)
            if _scan(text)[1]:
                for target in targets:
                    names.setdefault((scope(target), target.id), (text, _string(node) is not None, target))
                    held.add(target.id)

    for node in strings():
        bad, good = _scan(render(node))
        found += [f"{where}:{node.lineno}: {v}" for v in bad]
        for path in good:
            registered.setdefault(path, set()).add(f"{where}:{node.lineno}")
        if not good:
            continue
        if _string(node) is not None and not (binding(node) or filled(node) or isinstance(parent.get(node), ast.Expr)):
            found.append(f"{where}:{node.lineno}: {sorted(good)[0]}: a registered path used where the scan cannot follow it")
        elif _string(node) is None and changed(node):
            found.append(f"{where}:{node.lineno}: an address on {sorted(good)[0]} changed after it is built")

    for node in nodes:
        if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load) and (holds := bound(node)):
            text, bare, _ = holds
            name = getattr(node, "id", getattr(node, "attr", ""))
            if bare and not (rendered(node) or filled(node)):
                found.append(f"{where}:{node.lineno}: {name}: a registered path used where the scan cannot follow it")
            elif not bare and changed(node):
                found.append(f"{where}:{node.lineno}: {name}: an address on a registered path changed after it is built")
        elif isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load) and node.id in held:
            holds = names.get((scope(node), node.id))
            if holds and holds[1] and holds[2] is not node:
                found.append(f"{where}:{node.lineno}: {node.id}: a name bound to a registered path is bound again")
    return found, registered


def _scan_app(root: Path = APP) -> tuple[list[str], dict[str, set[str]], list[str]]:
    """What the gate finds in every file under ``root``, the registered paths it reads with where it
    reads them, and the files it reads, named from ``root``'s parent (``app/...``)."""
    files = sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    trees = {p: ast.parse(p.read_text(encoding="utf-8")) for p in files if p.suffix == ".py"}
    exported: dict[str, tuple[str, bool]] = {}
    for tree in trees.values():
        exported.update(_exports(tree))
    found: list[str] = []
    registered: dict[str, set[str]] = {}
    for path in files:
        where = str(path.relative_to(root.parent))
        if path in trees:
            bad, good = _scan_python(trees[path], where, exported)
        else:
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")  # a binary file, or text in a legacy encoding: read it all the same
            bad, seen = _scan(text)
            bad, good = [f"{where}: {v}" for v in bad], {p: {where} for p in seen}
        found += bad
        for path_, places in good.items():
            registered.setdefault(path_, set()).update(places)
    return found, registered, [str(p.relative_to(root.parent)) for p in files]


# The tile's path, and a constant bound to it, as the planted cases spell them.
_T = '_T = "/assets/earningsnerd-appicon.png"\n'
# (what, the files under app/ the case writes, "flag" or "pass" or "gap"): a string is app/form.py.
# "flag" breaks the rule, "pass" is a look-alike, "gap" breaks the rule out of the scan's reach (the
# header names each one).
FORMS: list[tuple[str, str | dict[str, str | bytes], str]] = [
    ("a whole registered path", 'P = "/assets/earningsnerd-appicon.png"', "pass"),
    ("an unregistered path", 'P = "/assets/earningsnerd-new.png"', "flag"),
    ("a path in an attribute", 'P = "<img src=\\"/assets/earningsnerd-new.png\\">"', "flag"),
    ("a name left open in an f-string", 'P = f"{base}/assets/{name}.png"', "flag"),
    ("a directory concatenated with a name", 'P = "/assets/" + name', "flag"),
    ("a directory constant", 'ASSETS = "/assets"', "flag"),
    ("a join", 'P = posixpath.join("/assets", name)', "flag"),
    ("a format template, the template's own spelling", 'P = "<img src=\\"{base}/assets/earningsnerd-new.png\\">".format(base=b)', "flag"),
    ("a %-template", 'P = "%s/assets/earningsnerd-new.png" % base', "flag"),
    ("a string.Template", 'P = Template("$base/assets/earningsnerd-new.png")', "flag"),
    ("a Jinja template", {"templates/mail/banner.html": '<img src="{{ base }}/assets/earningsnerd-new.png">'}, "flag"),
    ("a template in a legacy encoding", {"templates/mail/legacy.html": '© <img src="/assets/earningsnerd-new.png">'.encode("cp1252")}, "flag"),
    ("the second candidate of a srcset", 'P = "/assets/earningsnerd-appicon.png 1x, /assets/earningsnerd-new@2x.png 2x"', "flag"),
    ("a path behind an escaped quote", 'P = "src=&quot;/assets/earningsnerd-new.png&quot;"', "flag"),
    ("a CSS url()", 'P = "background:url(/assets/earningsnerd-new.png)"', "flag"),
    ("a registered name with a suffix", 'P = "/assets/earningsnerd-appicon.png;v=2"', "flag"),
    ("bytes", 'P = b"/assets/earningsnerd-new.png"', "flag"),
    ("another directory the site serves", 'P = "/icons/icon-192.png"', "flag"),
    ("a file at the site's root", 'P = "/og-image.png"', "flag"),
    ("an unregistered path in a non-route call", 'P = IMAGES.get("/assets/earningsnerd-new.png")', "flag"),
    ("a path posted by a client", 'P = client.post("/icons/icon-192.png")', "flag"),
    # Something filled in after a whole registered path.
    ("a field after a registered path in an f-string", 'P = f"{base}/assets/earningsnerd-appicon.png{suffix}"', "flag"),
    ("a suffix concatenated to a registered path", 'P = "/assets/earningsnerd-appicon.png" + suffix', "flag"),
    ("a format field after a registered path", 'P = "/assets/earningsnerd-appicon.png{}".format(suffix)', "flag"),
    ("a %-field after a registered path", 'P = "/assets/earningsnerd-appicon.png%s" % suffix', "flag"),
    ("a Template field after a registered path", 'P = Template("/assets/earningsnerd-appicon.png$suffix")', "flag"),
    # A registered path used other than whole: the binding forms of a name, and what the code does to it.
    ("a suffix added to a registered constant", _T + 'P = _T + "@2x.png"', "flag"),
    ("a registered constant read with a suffix in an f-string", _T + 'P = f"{base}{_T}@2x.png"', "flag"),
    ("a field after a registered constant", _T + 'P = f"{base}{_T}{suffix}"', "flag"),
    ("a registered constant changed by a method", _T + 'P = _T.replace("appicon", "appicon-dark")', "flag"),
    ("a registered constant sliced", _T + 'P = f"{base}{_T[:-4]}@2x.png"', "flag"),
    ("a registered constant handed to a function", _T + 'P = str(PurePosixPath(_T).with_name("earningsnerd-banner.png"))', "flag"),
    ("a directory taken from a registered constant", _T + "ASSETS = posixpath.dirname(_T)", "flag"),
    ("a registered constant converted in an f-string", _T + 'P = f"{base}{_T!s}"', "flag"),
    ("a registered constant bound again", _T + '_T = "/assets/earningsnerd-new.png"', "flag"),
    ("a registered constant added to in place", _T + '_T += "@2x.png"', "flag"),
    ("a registered constant as a loop's variable", _T + "for _T in variants:\n    pass", "flag"),
    ("a registered constant aliased", _T + "TILE = _T", "flag"),
    ("a registered constant imported and changed", {"a.py": _T, "b.py": 'from a import _T\nP = _T + "@2x.png"'}, "flag"),
    ("a registered constant imported under another name", {"a.py": _T, "b.py": 'from a import _T as TILE\nP = TILE.replace("appicon", "x")'}, "flag"),
    ("a registered constant read through its module", {"a.py": _T, "b.py": "import a\nP = a._T[:-4]"}, "flag"),
    ("a class's registered constant changed", 'class Mail:\n    TILE = "/assets/earningsnerd-appicon.png"\n\n    def url(self):\n        return self.TILE + "@2x.png"', "flag"),
    ("a function's registered path changed", 'def f():\n    t = "/assets/earningsnerd-appicon.png"\n    return t.replace("appicon", "x")', "flag"),
    ("a registered path handed to a function", 'P = _img("/assets/earningsnerd-appicon.png")', "flag"),
    ("a registered path in a container", 'P = ["/assets/earningsnerd-appicon.png"]', "flag"),
    ("a registered path in a destructuring", '_A, _B = "/assets/earningsnerd-appicon.png", "x"', "flag"),
    ("a registered path as a default", 'def f(p="/assets/earningsnerd-appicon.png"):\n    return p', "flag"),
    ("a registered path returned", 'def f():\n    return "/assets/earningsnerd-appicon.png"', "flag"),
    ("a registered path changed by a method", 'P = "/assets/earningsnerd-appicon.png".replace("appicon", "x")', "flag"),
    ("an address built on a registered path, changed", 'P = f"{base}/assets/earningsnerd-appicon.png".replace("appicon", "x")', "flag"),
    ("a name holding an address on a registered path, sliced", 'U = f"{base}/assets/earningsnerd-appicon.png"\nP = U[:-4] + "@2x.png"', "flag"),
    # An origin, a second slash or an unstripped FRONTEND_URL in front of the path.
    ("the apex in front of a registered path", 'P = "https://earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("www in front of a registered path", 'P = "https://www.earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("a protocol-relative origin", 'P = "//www.earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("plain http in capitals", 'P = "HTTP://WWW.EARNINGSNERD.IO/assets/earningsnerd-appicon.png"', "flag"),
    ("the site's host with no scheme", 'P = "www.earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("the API's host", 'P = "https://api.earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("a site origin concatenated before a path", 'P = "https://earningsnerd.io" + "/assets/earningsnerd-appicon.png"', "flag"),
    ("a site origin before a registered constant in an f-string", _T + 'P = f"https://earningsnerd.io{_T}"', "flag"),
    ("a site origin concatenated before a registered constant", _T + 'P = "https://www.earningsnerd.io" + _T', "flag"),
    ("a doubled slash after a base", 'P = f"{base}//assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL with its trailing slash kept", 'P = f"{settings.FRONTEND_URL}/assets/earningsnerd-mark-sage.png"', "flag"),
    ("FRONTEND_URL concatenated with its trailing slash kept", _T + "P = settings.FRONTEND_URL + _T", "flag"),
    # A placeholder host, or a placeholder token, in front of the path.
    ("an unregistered path after a host filled in by .format", 'P = "https://{host}/assets/earningsnerd-banner.png".format(host=h)', "flag"),
    ("an unregistered path after a host filled in by %", 'P = "https://%s/icons/icon-192.png" % h', "flag"),
    ("an unregistered path after a Template host", 'P = Template("https://$host/assets/earningsnerd-banner.png")', "flag"),
    ("an unregistered path after a Jinja host", {"templates/mail/host.html": '<img src="https://{{host}}/assets/earningsnerd-banner.png">'}, "flag"),
    ("an unregistered path after a protocol-relative filled-in host", 'P = "//{host}/icons/icon-192.png"', "flag"),
    ("an unregistered path after a %-token", 'P = "%BASE%/assets/earningsnerd-new.png"', "flag"),
    ("an unregistered path after an @-token", 'P = "@BASE@/assets/earningsnerd-new.png"', "flag"),
    ("an unregistered path after a dunder token", 'P = "__BASE__/assets/earningsnerd-new.png"', "flag"),
    # Look-alikes that must pass.
    ("a registered path on FRONTEND_URL", 'P = f"{settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"', "pass"),
    ("a registered constant read whole on FRONTEND_URL", _T + 'P = f"{settings.FRONTEND_URL.rstrip(\'/\')}{_T}"', "pass"),
    ("a registered constant concatenated on FRONTEND_URL", _T + 'P = settings.FRONTEND_URL.rstrip("/") + _T', "pass"),
    ("a registered constant with a query after it", _T + 'P = f"{base}{_T}?v=2"', "pass"),
    ("a registered constant imported and read whole", {"a.py": _T, "b.py": 'from a import _T\nP = f"{base}{_T}"'}, "pass"),
    ("a registered template filled by .format", 'IMG = \'<img src="{base}/assets/earningsnerd-appicon.png">\'\nP = IMG.format(base=b)', "pass"),
    ("an address built on a registered path, handed on", 'P = _wrap(f\'<img src="{settings.FRONTEND_URL.rstrip("/")}/assets/earningsnerd-appicon.png">\')', "pass"),
    ("a name holding an address, read whole", 'U = f"{base}/assets/earningsnerd-appicon.png"\nP = f"<img src=\\"{U}\\">"', "pass"),
    ("a registered path with a query", 'P = "/assets/earningsnerd-appicon.png?v=2"', "pass"),
    ("a registered path ending a sentence", 'P = "The header shows /assets/earningsnerd-appicon.png."', "pass"),
    ("a docstring", 'def f():\n    """Shows /assets/earningsnerd-new.png."""', "pass"),
    ("a comment", "# /assets/earningsnerd-new.png\nX = 1", "pass"),
    ("a route of the API", '@router.get("/favicon.ico")\nasync def favicon(): ...', "pass"),
    ("the backend's own file path", 'P = "app/assets/fonts/Inter-Variable-latin.woff2"', "pass"),
    ("the frontend's file path", 'P = "frontend/public/assets/earningsnerd-new.png"', "pass"),
    ("another site's file", 'P = "https://cdn.example.com/assets/earningsnerd-new.png"', "pass"),
    ("a sub-path of another URL", 'P = "https://www.sec.gov/Archives/assets/x.htm"', "pass"),
    ("a directory's name in prose", 'P = "current assets/liabilities"', "pass"),
    ("a longer name that starts like a directory", 'P = "/assets-manifest.json"', "pass"),
    ("an unrelated name with a method", _T + 'P = f"{base}{_T}"\nQ = name.replace("a", "b")', "pass"),
    # Out of the scan's reach.
    ("no slash before the path", 'P = urljoin(base + "/", "assets/earningsnerd-new.png")', "gap"),
    ("a registered path on another origin's variable", 'P = f"{settings.API_BASE_URL}/assets/earningsnerd-appicon.png"', "gap"),
    ("a registered path after another origin filled in as a host", 'P = "https://{host}/assets/earningsnerd-appicon.png".format(host=h)', "gap"),
    ("a path after a bare word", 'P = "BASE_URL/assets/earningsnerd-new.png"', "gap"),
    ("an address a function hands back, changed by its caller", 'def u():\n    return f"{base}/assets/earningsnerd-appicon.png"\n\nP = u().replace("appicon", "x")', "gap"),
    ("a path the site serves from a route", 'P = "/manifest.webmanifest"', "gap"),
]
# One case for each character the header says a URL path can start after. The list is written here,
# not taken from _DELIMITERS, so narrowing that set fails a case.
FORMS += [(f"a path after {c!r}", f"P = {'x' + c + '/assets/earningsnerd-new.png'!r}", "flag") for c in " \t\r\n\"'`<>()[]=:,;}"]


def test_the_scan_scores_every_planted_form(tmp_path):
    wrong = []
    for number, (what, files, outcome) in enumerate(FORMS):
        root = tmp_path / str(number) / "app"
        for name, source in ({"form.py": files} if isinstance(files, str) else files).items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(source if isinstance(source, bytes) else source.encode("utf-8"))
        found = _scan_app(root)[0]
        if bool(found) != (outcome == "flag"):
            wrong.append(f"{what}: expected {'flagged' if outcome == 'flag' else 'clean'}, got {found or 'clean'}")
    assert not wrong, "the scan no longer scores its planted forms:\n" + "\n".join(wrong)
    gaps = {what for what, _, outcome in FORMS if outcome == "gap"}
    assert gaps == {
        "no slash before the path",
        "a registered path on another origin's variable",
        "a registered path after another origin filled in as a host",
        "a path after a bare word",
        "an address a function hands back, changed by its caller",
        "a path the site serves from a route",
    }, "the header names each gap the cases mark: keep the two in step"


def test_mail_addresses_the_site_only_by_registered_paths():
    assert {"assets", "icons"} <= set(SITE_NAMES), f"frontend/public no longer reads as the site's files: {SITE_NAMES}"
    found, registered, read = _scan_app()
    walked = {"app/services/email_service.py", "app/assets/fonts/OFL.txt", "app/data/index_membership.json", "app/assets/brand/earningsnerd-mark.png"}
    assert walked <= set(read) and len(read) > 200, f"the walk no longer reads every file in backend/app: {len(read)} read"
    assert not found, (
        "these strings address a file of the site's other than by a whole registered path on FRONTEND_URL, used "
        "whole. Register a path mail shows in frontend/tests/unit/publishedAssetUrls.json in the same PR, spell it "
        "whole and build it on settings.FRONTEND_URL.rstrip('/') (LOGO_README.md › Published URLs stay put). A "
        "string here that is no address mail carries narrows this gate by its shape, never by its name, with a "
        "planted case (lessons/arch-gate-reference-values-are-themselves-gated.md):\n" + "\n".join(found)
    )
    assert any(place.startswith("app/services/email_service.py:") for place in registered.get(email_service._HEADER_TILE_PATH, ())), (
        f"the scan no longer reads the mail header's tile as a registered path in email_service.py: {registered}"
    )


def test_the_tile_follows_frontend_url_whose_default_is_the_registers_origin(monkeypatch):
    assert Settings.model_fields["FRONTEND_URL"].default == ORIGIN, (
        "FRONTEND_URL's default is the origin production runs on (it sets none), and sent mail keeps the "
        "whole address: keep it the register's origin, the one that answers without a redirect"
    )
    for origin in (ORIGIN, "https://frontend.example.test"):
        for configured in (origin, f"{origin}/"):
            monkeypatch.setattr(settings, "FRONTEND_URL", configured)
            sources = re.findall(r'<img src="([^"]+)"', email_service._wrap_html("<p>Body</p>"))
            assert sources == [f"{origin}{email_service._HEADER_TILE_PATH}"], (
                f"FRONTEND_URL={configured!r} gave the header's image {sources}"
            )
