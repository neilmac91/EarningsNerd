"""Gate: the code spells a file of the site's only as a registered path, built on FRONTEND_URL.

Sent mail keeps every address it carries for as long as the message is kept, and nobody can edit it
after sending, so a file of the site's that the backend puts in mail is published: its path must never
move or change (``frontend/public/assets/LOGO_README.md`` › Published URLs stay put). The register,
``frontend/tests/unit/publishedAssetUrls.json``, names the published paths and the origin mail
addresses them on, and ``frontend/tests/unit/publishedAssetUrls.spec.ts`` holds each path to its
file's bytes and keeps the middleware and every redirect and rewrite off it. Two gates hold the backend
to the rule's mail half (CLAUDE.md rule 12):
- this one reads the code: every file in ``backend/app``, mail or not;
- ``test_mail_rendered_addresses.py`` reads the mail. It renders every public function of
  ``email_service.py``, the module that builds it, through every line of the module, and reads each
  address in what is sent, so it checks an address however the code derived it, within the limits its
  header names. This scan cannot follow a value through the code.

This scan reads the Python's strings as the code builds them, docstrings and the paths of the API's route
decorators aside: an f-string or a ``+`` chain whole, a template ``textwrap.dedent`` or ``inspect.cleandoc``
re-indents (each known by the module's imports, not by its name alone) or ``.strip()`` strips of whitespace as
written, and a name bound to a registered path, or to an address built on one, read as what it holds, in its
module or in one that imports it from that module (an import of the name, or of the module, relative or not).
A name a function or a comprehension binds as its own (a parameter, an assignment, a loop's or a
comprehension's variable, a ``def``'s or a ``class``'s name, an import, an ``except``'s name, a ``match``'s
capture) shadows one bound further out, and its defaults, annotations and decorators, like a comprehension's
first iterable and a class's decorators and bases, are read in the scope around it; a walrus in a
comprehension binds in the scope around it, and ``global`` and ``nonlocal``, in a function or a class's body,
bind the name where they name it: the module, or the nearest function around that binds it. A class's body
binds the class's attributes, which the body reads once it has bound them, and the scope around's names before
that; ``self.``, ``cls.``, ``type(self)``, the class's name and an instance of it (``C()``) read them, a
class's own first and then its bases', in the class's module and in one that imports the class or a subclass
of it. It reads every other file's text. In them:

- the path of a file the site serves from ``frontend/public``, or of one of its directories, where a
  URL path can start (the start of a string, after whitespace, a quote or a backtick, a bracket, "=",
  ":", ",", ";", or a placeholder such as ``{base}``, ``%s``, ``$base``, ``__BASE__`` or a host the code
  fills in, ``https://{host}``) spells a whole registered path, and nothing is filled in after it. A
  directory left open for a name to follow (``"/assets/"``, ``f"{base}/icons/{name}"``) fails, so a
  path composed at run time has to be written out whole;
- no origin of the site's (``earningsnerd.io`` or any host under it, with or without a scheme), no
  second slash and no ``FRONTEND_URL`` that keeps its trailing slash comes in front of such a path: mail
  builds it on ``FRONTEND_URL`` with the slash stripped, and a doubled slash answers 308. The scan
  reads ``FRONTEND_URL`` where the f-string or the concatenation names it, read as it is (``str()``,
  ``!s``, ``:s``, or a conditional, an ``or`` or an ``and`` that may yield it), and counts it stripped
  only under ``.rstrip()`` or ``.strip()`` with "/" among its characters, or ``.removesuffix("/")``;
- a registered path is used whole. Its string may sit in the f-string or the concatenation that builds an
  address, in a template a ``.format``, ``%`` or ``string.Template`` fills, or in a name bound to it once,
  which is then read only in those places. A string with nothing in front of the path counts as the path,
  and literals joined with ``+``, or an f-string with no fields, are one string. A comparison reads it, as a
  ``match``'s subject or case, or in what the comparison holds (a tuple, a list, a set, a dict's keys, or a
  ``frozenset()``, ``set()``, ``tuple()`` or ``list()`` of one, at any depth). Every other use the scan sees
  fails: an argument, a container's item, a default, a return value, a slice, a method other than a read
  (``startswith``, ``find``) or a strip of whitespace alone, which it passes through, or a format spec other
  than ``:s`` applied to it, a second binding (an assignment, a ``def`` or a ``class``, an import, an
  ``except``'s name or a ``match``'s capture, in the scope or the class body that binds it, or through
  ``global`` or ``nonlocal``, or an attribute another module sets or deletes), a setting the environment can
  replace. A template re-indented or stripped of whitespace is what it is built from: a string, or a name
  bound to one. An address built on one may be handed on, but a slice, a format spec, or a method other than
  a read or a strip or a replacement of whitespace fails on it, where it is built, where a template's fill
  builds it, or through a name that holds it. What is added to it is read with it, as the concatenation, or
  the in-place addition, builds it.

The header's tile follows ``FRONTEND_URL`` whatever it is set to, with a trailing slash stripped, and
``FRONTEND_URL``'s default is the register's origin.

``FORMS`` plants a case for each way the rule can be broken and each look-alike that must pass.
``test_the_scan_scores_every_planted_form`` writes each case into a directory and scores it through the
walk that reads ``backend/app``. Out of the scan's reach, and planted as gaps, one case each:
- no slash before the path: ``urljoin(base + "/", "assets/x.png")``
- a path after a bare word: ``BASE_URL/assets/x.png``, which reads like a file path
- a path spelled with a dot segment or a percent-escape: ``/./assets/``, ``/x/../assets/``, ``%61ssets``
- a registered path followed by a character the scan reads as its end: ``,``, ``|`` or a backslash
- a JSON file's escaped slashes: ``\\/assets\\/``
- a data file's path, changed by the code that reads it
- a registered path on another origin's variable: the scan reads the path, not what is filled in before it
- a registered path after another origin filled in as a host
- FRONTEND_URL read through a name, a call or a conversion that quotes it: an alias, a parameter's default, a
  function's return, ``getattr``, ``format()``, ``!r``
- FRONTEND_URL filled into a template: ``.format(base=settings.FRONTEND_URL)``, ``%``
- an address a function hands back, changed by its caller: a helper's return, ``substitute()`` on a ``Template`` held in a name
- an address handed to a function that changes it: a helper, ``re.sub``, ``str.replace(u, ...)``, a join
- an address held in a container, an attribute or a conditional, then changed: a list, a dict, ``self.u``, ``x if c else y``, a walrus
- an address filled into another template, with a suffix: ``"{}@2x.png".format(u)``, ``%``, ``Template``
- a name bound to a registered path, rebound where the scan does not look: ``setattr``, ``globals()`` or ``vars()``,
  ``__dict__``
- a name read through getattr or globals()
- a class's attribute read through an instance held in a name, or a class nested in another: ``m = C(); m.TILE``,
  ``Outer.Inner.TILE``
- a Jinja filter applied to a path: ``| replace``, ``~``
- a path the site serves from a route: ``app/manifest.ts``

The rendered gate checks what each of these puts in the mail it renders, within the limits its header
names, save a path after a bare word, which is no address, and a path a route serves, which the register
does not hold. Whether the register's origin answers without a redirect is review-checked: this suite
runs offline.
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
# entity for a quote or for markup, a placeholder or an escape. Anything else (";", "@", "+", "&", "&amp;")
# is read into the path, as a client reads it.
_PATH = re.compile(r"""(?:[^\s"'`<>()\[\],?#&{}%$\\|^]|&(?!(?:quot|apos|lt|gt|#0*3[49]|#x0*2[27]);))*""", re.IGNORECASE)
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
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, *_COMPREHENSIONS)
_DEDENTS = {"textwrap.dedent", "inspect.cleandoc"}  # they change a template's indentation alone
_READS = {"startswith", "endswith", "find", "rfind", "index", "rindex", "count"}  # hand back no part of it
_WHITESPACE_STRIPS = {"strip", "lstrip", "rstrip"}  # called with no argument, they leave an address whole
_SUBSTITUTES = {"substitute", "safe_substitute"}  # string.Template's fills


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


Exports = dict[tuple[str, str], tuple[str, bool]]  # (module, name) -> (what it holds, whether it is bare)


def _scan_python(
    tree: ast.Module, where: str, exported: Exports, *, module: str, exports_only: bool = False
) -> tuple[list[str], dict[str, set[str]], Exports]:
    """What the scan finds in ``module``, the registered paths it reads there with where, and the names it
    binds outside any function (in its body, a class, an if, a try) to a registered path or to an address
    built on one, which another module may import: each with what it holds and whether it is bare."""
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
    # one, the target that binds it); a scope is the function that binds the name, the class whose body
    # binds it as an attribute, or None, the module.
    names: dict[tuple[ast.AST | None, str], tuple[str, bool, ast.AST | None]] = {}
    held: set[str] = set()  # the names in ``names``, for a quick test before a scope is looked up
    package = module if where.endswith("__init__.py") else module.rpartition(".")[0]
    class_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    def source(node: ast.ImportFrom) -> str:
        """The module an import names, a relative one resolved from this module's package."""
        if not node.level:
            return node.module or ""
        parts = package.split(".") if package else []
        base = parts[: len(parts) - (node.level - 1)]
        return ".".join([*base, *([node.module] if node.module else [])])

    # The names this module binds to a module: import a.b as c, from a import b (b may be a module).
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    modules[alias.asname] = alias.name
                else:
                    head = alias.name.split(".")[0]
                    modules[head] = head
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                modules[alias.asname or alias.name] = f"{source(node)}.{alias.name}"

    def dotted(node: ast.AST) -> str | None:
        """The module ``node`` names, through the names this module binds to modules."""
        if isinstance(node, ast.Name):
            return modules.get(node.id)
        if isinstance(node, ast.Attribute) and (head := dotted(node.value)) is not None:
            return f"{head}.{node.attr}"
        return None

    def inside(up: ast.AST, child: ast.AST, below: ast.AST | None) -> bool:
        """Whether ``child``, the node under the scope ``up`` on the way down to ``below``, is evaluated in that
        scope: a function's body, a lambda's, a comprehension's all but its first iterable. A function's
        defaults, annotations and decorators are evaluated in the scope around it."""
        if isinstance(up, ast.Lambda):
            return child is up.body
        if isinstance(up, _COMPREHENSIONS):
            return not (child is up.generators[0] and below is up.generators[0].iter)
        return any(child is statement for statement in up.body)

    def scope(node: ast.AST) -> ast.AST | None:
        """The function or comprehension ``node`` is evaluated in, or None, the module."""
        below, child, up = None, node, parent.get(node)
        while up is not None and not (isinstance(up, _SCOPES) and inside(up, child, below)):
            below, child, up = child, up, parent.get(up)
        return up

    def binds(node: ast.AST) -> list[str]:
        """The names a statement or a pattern binds, assignments aside: a def's or a class's name, an import's,
        an except's, a match's capture."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return [node.name]
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return [alias.asname or alias.name.split(".")[0] for alias in node.names]
        if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            return [node.name] if node.name else []
        if isinstance(node, ast.MatchMapping):
            return [node.rest] if node.rest else []
        return []

    def body_class(node: ast.AST | None) -> ast.ClassDef | None:
        """The class whose body a binding at ``node`` is made in: it binds the class's attribute, not a name of
        the scope around the class."""
        below, child, up = None, node, parent.get(node) if node is not None else None
        while up is not None:
            if isinstance(up, ast.ClassDef) and any(child is statement for statement in up.body):
                return up  # its decorators, bases and keywords are read in the scope around it
            if isinstance(up, _SCOPES) and inside(up, child, below):
                return None
            below, child, up = child, up, parent.get(up)
        return None

    def statement(node: ast.AST, klass: ast.ClassDef) -> int | None:
        """Where in a class's body the statement that holds ``node`` stands, or None outside the body."""
        child, up = node, parent.get(node)
        while up is not None and up is not klass:
            child, up = up, parent.get(up)
        return next((i for i, line in enumerate(klass.body) if line is child), None) if up is klass else None

    def home(node: ast.AST) -> ast.AST | None:
        """The scope a binding at ``node`` is made in: a walrus in a comprehension binds in the scope around it."""
        here = scope(node)
        if isinstance(node, ast.Name) and isinstance(parent.get(node), ast.NamedExpr):
            while isinstance(here, _COMPREHENSIONS):
                here = scope(here)
        return here

    # The globals and nonlocals each scope or class body declares, which it does not bind as its own.
    declared: dict[ast.AST | None, dict[str, bool]] = {}  # scope or class -> name -> whether it is global
    for node in nodes:
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                declared.setdefault(body_class(node) or scope(node), {})[name] = isinstance(node, ast.Global)

    # The names each function or comprehension binds as its own, which shadow a binding further out, and the
    # names each class's body binds, with the first statement that binds each, after which its body reads the
    # class's own.
    own: dict[ast.AST, set[str]] = {}
    class_own: dict[ast.ClassDef, dict[str, int]] = {}
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            args = node.args
            own.setdefault(node, set()).update(a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg) if a)
        stored = [(home(node), node.id)] if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load) else []
        for here, name in stored + [(scope(node), name) for name in binds(node)]:
            if (klass := body_class(node)) is not None:
                if name not in declared.get(klass, {}):
                    first, at = class_own.setdefault(klass, {}), statement(node, klass)
                    first[name] = min(first.get(name, at), at)
            elif here is not None and name not in declared.get(here, {}):
                own.setdefault(here, set()).add(name)

    # (scope, name) -> the scope a global or a nonlocal there binds the name in: the module, or the nearest
    # function around it that binds the name as its own.
    outward: dict[tuple[ast.AST | None, str], ast.AST | None] = {}
    for here, names_declared in declared.items():
        for name, is_global in names_declared.items():
            there = None if is_global else scope(here)
            while there is not None and (isinstance(there, _COMPREHENSIONS) or name not in own.get(there, ())):
                there = scope(there)
            outward[(here, name)] = there

    def binder(node: ast.AST, name: str) -> ast.AST | None:
        """The scope a name bound at ``node`` lives in: the class whose body binds it as an attribute, the one it
        is bound in, or the one a global or a nonlocal there names."""
        if (klass := body_class(node)) is not None:
            return outward.get((klass, name), klass)
        here = home(node)
        return outward.get((here, name), here)

    def module_class(node: ast.AST) -> ast.ClassDef | None:
        """The class of this module a name or a call of it names, where no function binds the name."""
        if isinstance(node, ast.Call):
            node = node.func  # an instance's attribute is its class's, unless it sets its own
        if isinstance(node, ast.Name):
            return next((klass for klass in class_nodes if klass.name == node.id and scope(klass) is None and body_class(klass) is None), None)
        return None

    def attributes(klass: ast.ClassDef, seen: frozenset = frozenset()) -> set[str]:
        """The names under which a class's attributes, its own or its bases', may hold a registered path, which
        ``attribute`` reads."""
        found = {name for (where_bound, name) in names if where_bound is klass}
        for base in klass.bases:
            if (inner := module_class(base)) is not None and inner not in seen:
                found |= attributes(inner, seen | {klass})
            elif (owner := dotted(base)) is not None:
                found |= {name for (exporter, name) in exported if exporter == owner}
        return found

    def attribute(klass: ast.ClassDef, name: str, seen: frozenset = frozenset()) -> tuple[str, bool, ast.AST | None] | None:
        """What a class's attribute holds, its own or one a base it names gives it: a class of this module's, or
        one another module exports."""
        if (klass, name) in names:
            return names[(klass, name)]
        if name in class_own.get(klass, {}):
            return None  # the class's own attribute, which holds no registered path
        for base in klass.bases:
            if (inner := module_class(base)) is not None and inner not in seen:
                if (holds := attribute(inner, name, seen | {klass})) is not None:
                    return holds
            elif (owner := dotted(base)) is not None and (owner, name) in exported:
                return (*exported[(owner, name)], None)
        return None

    def bound(node: ast.AST) -> tuple[str, bool, ast.AST | None] | None:
        if isinstance(node, ast.Name) and node.id in held:
            if (klass := body_class(node)) is not None:
                if (klass, node.id) in names:
                    return names[(klass, node.id)]  # a class's body reads its own attributes first
                first = class_own.get(klass, {}).get(node.id)
                if first is not None and first < (statement(node, klass) or 0):
                    return None  # read after its own binding of the name, which holds no registered path
            here = scope(node)
            while (here, node.id) not in names and here is not None:
                if node.id in own.get(here, ()):  # its own name here shadows a binding further out
                    return None
                here = scope(here)
            return names.get((here, node.id))
        if isinstance(node, ast.Attribute):
            # A class's attribute, its own or a base's: read through an instance or the class in a method, by the
            # class's name or an instance of it, or from another module that imports the class.
            around = isinstance(node.value, ast.Name) and node.value.id in ("self", "cls")
            around |= (
                isinstance(node.value, ast.Call) and getattr(node.value.func, "id", None) == "type" and len(node.value.args) == 1
                and getattr(node.value.args[0], "id", None) in ("self", "cls")
            )
            if around:
                owners, up = [], parent.get(node)
                while up is not None and not owners:
                    owners, up = [up] if isinstance(up, ast.ClassDef) else [], parent.get(up)
            else:
                owners = [klass for klass in class_nodes if isinstance(node.value, ast.Name) and klass.name == node.value.id]
                owners += [klass] if (klass := module_class(node.value)) is not None and klass not in owners else []
            for klass in owners:
                if (holds := attribute(klass, node.attr)) is not None:
                    return holds
            target = node.value.func if isinstance(node.value, ast.Call) else node.value
            if (owner := dotted(target)) is not None and (owner, node.attr) in exported:
                return (*exported[(owner, node.attr)], None)
        return None

    def render(node: ast.AST) -> str:
        """The text an f-string or a ``+`` chain builds, a name bound to a registered path read as it."""
        if (text := _string(node)) is not None:
            return text
        if isinstance(node, ast.JoinedStr):
            return "".join(render(value) for value in node.values)
        if isinstance(node, ast.FormattedValue):
            if not plain(node):
                return _FIELD  # a format spec may cut or pad what it reads
            return f"'{render(node.value)}'" if node.conversion in (ord("r"), ord("a")) else render(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return render(node.left) + render(node.right)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return render(node.left)  # a %-template filled: its text, placeholders and all
        if getattr(node, "attr", getattr(node, "id", None)) == "FRONTEND_URL":
            return _UNSTRIPPED
        if isinstance(node, (ast.IfExp, ast.BoolOp)):  # one of its values, the scan cannot tell which
            if isinstance(node, ast.IfExp):
                values = [node.body, node.orelse]
            else:  # an "and" yields an earlier value only when it is empty, so its last one is read
                values = node.values if isinstance(node.op, ast.Or) else node.values[-1:]
            return _UNSTRIPPED if any(render(value).endswith(_UNSTRIPPED) for value in values) else _FIELD
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "str" and len(node.args) == 1 and not node.keywords:
            return render(node.args[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and render(node.func.value) == _UNSTRIPPED:
            arg = _string(node.args[0]) if len(node.args) == 1 and not node.keywords else None
            strips = (node.func.attr in ("rstrip", "strip") and arg is not None and "/" in arg) or (node.func.attr == "removesuffix" and arg == "/")
            return _FIELD if strips else _UNSTRIPPED
        if stripped(node):
            return render(node.func.value)  # whitespace off its ends: its text as written
        if dedented(node):
            return render(node.args[0])  # re-indented: its text as written
        if (template := filled_template(node)) is not None:
            return render(template)  # a template filled by .format or Template: its text, placeholders and all
        return holds[0] if (holds := bound(node)) else _FIELD

    def plain(value: ast.FormattedValue) -> bool:
        """Whether an f-string's field reads its value as it is: no format spec, or ``:s``."""
        spec = value.format_spec
        return spec is None or (len(spec.values) == 1 and _string(spec.values[0]) == "s")

    def filled_template(node: ast.AST) -> ast.AST | None:
        """The template ``node`` fills: ``t.format(...)``, ``t.format_map(...)``, ``Template(t).substitute(...)``."""
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            return None
        if node.func.attr in _FILLS:
            return node.func.value
        inner = node.func.value
        if node.func.attr in _SUBSTITUTES and isinstance(inner, ast.Call) and getattr(inner.func, "attr", getattr(inner.func, "id", None)) == "Template" and inner.args:
            return inner.args[0]
        return None

    def dedented(node: ast.AST | None) -> bool:
        """Whether ``node`` re-indents one template, ``textwrap.dedent(t)`` or ``inspect.cleandoc(t)``, read
        through the module's imports, so a function of another's that takes the name is no such call."""
        return isinstance(node, ast.Call) and dotted(node.func) in _DEDENTS and len(node.args) == 1 and not node.keywords

    def stripped(node: ast.AST | None) -> bool:
        """Whether ``node`` strips whitespace alone off a string's ends, ``t.strip()``, which leaves it whole."""
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _WHITESPACE_STRIPS
            and not node.args
            and not node.keywords
        )

    def rendered(node: ast.AST) -> bool:
        """Whether ``node`` is part of the f-string, the ``+`` chain, the re-indented template or the strip of
        whitespace around it, which is read whole."""
        up = parent.get(node)
        if dedented(up) and up.args[0] is node:
            return True
        if isinstance(up, ast.Attribute) and up.value is node and stripped(parent.get(up)) and parent[up].func is up:
            return True
        if isinstance(up, ast.FormattedValue):
            return up.value is node and plain(up) and isinstance(parent.get(up), ast.JoinedStr)
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
        """Whether an index, a slice or a method is applied to ``node``, other than a fill, a read or a
        strip of whitespace alone."""
        up = parent.get(node)
        if isinstance(up, ast.Subscript):
            return up.value is node
        if not (isinstance(up, ast.Attribute) and up.value is node) or up.attr in _FILLS | _SUBSTITUTES | _READS:
            return False
        call = parent.get(up)
        if not (isinstance(call, ast.Call) and call.func is up):
            return True
        if up.attr in _WHITESPACE_STRIPS and not call.args and not call.keywords:
            return False  # whitespace off the ends leaves an address whole
        # Whitespace replaced, such as a page's line breaks, leaves an address whole too.
        return not (up.attr == "replace" and call.args and (_string(call.args[0]) or "x").isspace())

    def reads(node: ast.AST) -> bool:
        """Whether ``node`` is read and left as it is: compared, as a ``match``'s subject or case or in what a
        comparison holds (a tuple, a list, a set, a dict's keys, or a ``frozenset()``, ``set()``, ``tuple()`` or
        ``list()`` of one, at any depth), or given a method that changes nothing (``startswith``, ``find``)."""
        up = parent.get(node)
        if isinstance(up, ast.Attribute) and up.value is node and up.attr in _READS:
            return True
        if isinstance(up, ast.Match) and up.subject is node:
            return True  # compared with its cases
        child = node
        while True:
            if isinstance(up, (ast.Compare, ast.MatchValue)):
                return True
            held_in = isinstance(up, (ast.Tuple, ast.List, ast.Set)) or (isinstance(up, ast.Dict) and any(key is child for key in up.keys))
            collected = (
                isinstance(up, ast.Call) and getattr(up.func, "id", None) in ("frozenset", "set", "tuple", "list")
                and len(up.args) == 1 and up.args[0] is child and not up.keywords
            )
            if not (held_in or collected):
                return False
            child, up = up, parent.get(up)

    def converted(node: ast.AST) -> bool:
        """Whether an f-string's field reads ``node`` through a format spec, which may cut it."""
        up = parent.get(node)
        return isinstance(up, ast.FormattedValue) and up.value is node and not plain(up)

    def literal(node: ast.AST) -> bool:
        """Whether ``node`` is a string however it is written: a literal, literals joined with ``+``, or an
        f-string with no fields."""
        if _string(node) is not None:
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return literal(node.left) and literal(node.right)
        return isinstance(node, ast.JoinedStr) and all(_string(value) is not None for value in node.values)

    def bare(node: ast.AST, text: str) -> bool:
        """Whether ``node`` builds a registered path itself, with nothing in front of it, not an address: a
        string, a name bound to one, or a template re-indented or stripped of whitespace from either."""
        if literal(node) or text.startswith(tuple(REGISTERED)):
            return True
        if dedented(node) or stripped(node):
            inner = node.args[0] if dedented(node) else node.func.value
            return bare(inner, render(inner))
        return bool((holds := bound(node)) and holds[1])

    def in_settings(node: ast.AST) -> bool:
        """Whether ``node`` sits in a settings class's body, whose fields the environment can replace."""
        up = parent.get(node)
        while up is not None and not isinstance(up, (ast.ClassDef, *_SCOPES)):
            up = parent.get(up)
        return isinstance(up, ast.ClassDef) and any(
            getattr(base, "id", getattr(base, "attr", "")).endswith("Settings") for base in up.bases
        )

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
            if (_string(node) is not None or isinstance(node, ast.JoinedStr) or (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)) or dedented(node) or stripped(node))
            and id(node) not in skip
            and not rendered(node)
        ]

    def bind() -> bool:
        """Record each name bound to a registered path or to an address built on one; whether any was new."""
        new = False
        for node in nodes:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    key = (binder(node, alias.asname or alias.name), alias.asname or alias.name)
                    if (source(node), alias.name) in exported and key not in names:
                        names[key], new = (*exported[(source(node), alias.name)], None), True
                        held.add(key[1])
            elif targets := binding(node):
                text = render(node)
                if not _scan(text)[1]:
                    continue
                for target in targets:
                    key = (binder(target, target.id), target.id)
                    if key not in names:
                        names[key], new = (text, bare(node, text), target), True
                        held.add(target.id)
        return new

    while bind():  # a binding the walk reaches before the one it reads is read on the next pass
        pass
    exports = {(module, name): holds[:2] for (where_bound, name), holds in names.items() if where_bound is None}
    for klass in class_nodes:
        if scope(klass) is None and body_class(klass) is None:  # a class of the module's own, which it exports
            for name in attributes(klass):
                if (holds := attribute(klass, name)) is not None:
                    exports[(f"{module}.{klass.name}", name)] = holds[:2]
    if exports_only:
        return [], {}, exports

    for node in strings():
        text = render(node)
        bad, good = _scan(text)
        found += [f"{where}:{node.lineno}: {v}" for v in bad]
        for path in good:
            registered.setdefault(path, set()).add(f"{where}:{node.lineno}")
        if not good:
            continue
        if bare(node, text) and not (binding(node) or filled(node) or reads(node) or isinstance(parent.get(node), ast.Expr)):
            found.append(f"{where}:{node.lineno}: {sorted(good)[0]}: a registered path used where the scan cannot follow it")
        elif not bare(node, text) and (changed(node) or converted(node)):
            found.append(f"{where}:{node.lineno}: an address on {sorted(good)[0]} changed after it is built")
        if bare(node, text) and in_settings(node):
            found.append(f"{where}:{node.lineno}: {sorted(good)[0]}: a registered path in a setting the environment can replace")

    for node in nodes:  # an address a template's fill builds, changed where it is built
        fill = (filled_template(node) is not None) or (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod))
        if fill and (changed(node) or converted(node)) and (good := _scan(render(node))[1]):
            found.append(f"{where}:{node.lineno}: an address filled on {sorted(good)[0]} changed after it is built")

    for node in nodes:
        if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load) and (holds := bound(node)):
            is_bare = holds[1]
            name = getattr(node, "id", getattr(node, "attr", ""))
            if is_bare and not (rendered(node) or filled(node) or reads(node)):
                found.append(f"{where}:{node.lineno}: {name}: a registered path used where the scan cannot follow it")
            elif not is_bare and (changed(node) or converted(node)):
                found.append(f"{where}:{node.lineno}: {name}: an address on a registered path changed after it is built")
        elif isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load) and node.id in held:
            holds = names.get((binder(node, node.id), node.id))
            if holds and holds[1] and holds[2] is not node:
                found.append(f"{where}:{node.lineno}: {node.id}: a name bound to a registered path is bound again")
            elif holds and holds[2] is not node and isinstance(grown := parent.get(node), ast.AugAssign):
                # Added to in place, it is read as "x = x + ...": only what the addition breaks is found.
                before = set(_scan(holds[0])[0])
                after = _scan(holds[0] + render(grown.value))[0] if isinstance(grown.op, ast.Add) else ["changed in place"]
                found += [f"{where}:{node.lineno}: {node.id}: {v}" for v in after if v not in before]
        elif rebound := [name for name in binds(node) if name in held]:
            # The import that brings in an exported name is that name's binding, not a second one.
            imported = (
                {alias.asname or alias.name for alias in node.names if (source(node), alias.name) in exported}
                if isinstance(node, ast.ImportFrom)
                else set()
            )
            for name in rebound:
                holds = names.get((binder(node, name), name))
                if holds and holds[1] and name not in imported:
                    found.append(f"{where}:{node.lineno}: {name}: a name bound to a registered path is bound again")
        elif isinstance(node, ast.Attribute) and not isinstance(node.ctx, ast.Load) and (holds := bound(node)) and holds[1]:
            found.append(f"{where}:{node.lineno}: {node.attr}: a name bound to a registered path is bound again")
    return found, registered, exports


def _text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")  # a binary file, or text in a legacy encoding: read it all the same


def _scan_app(root: Path = APP) -> tuple[list[str], dict[str, set[str]], dict[str, int]]:
    """What the gate finds in every file under ``root``, the registered paths it reads with where it
    reads them, and how many characters of each file it reads, the files named from ``root``'s parent
    (``app/...``)."""
    files = sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    texts = {p: _text(p) for p in files}
    trees = {p: ast.parse(texts[p]) for p in files if p.suffix == ".py"}
    wheres = {p: str(p.relative_to(root.parent)) for p in files}
    modules = {p: ".".join(Path(wheres[p]).with_suffix("").parts).removesuffix(".__init__") for p in trees}
    exported: Exports = {}
    while True:  # a module may bind a name to one it imports, so the exports are read to a fixpoint
        new: Exports = {}
        for p, tree in trees.items():
            for key, holds in _scan_python(tree, wheres[p], exported, module=modules[p], exports_only=True)[2].items():
                if key not in exported:
                    new[key] = holds
        if not new:
            break
        exported.update(new)
    found: list[str] = []
    registered: dict[str, set[str]] = {}
    scanned: dict[str, int] = {}
    for path in files:
        where = wheres[path]
        if path in trees:
            bad, good, _ = _scan_python(trees[path], where, exported, module=modules[path])
        else:
            bad, seen = _scan(texts[path])
            bad, good = [f"{where}: {v}" for v in bad], {p: {where} for p in seen}
        scanned[where] = len(texts[path])
        found += bad
        for path_, places in good.items():
            registered.setdefault(path_, set()).update(places)
    return found, registered, scanned


# The tile's path, and a constant bound to it, as the planted cases spell them.
_T = '_T = "/assets/earningsnerd-appicon.png"\n'
# A class that holds the tile's path as an attribute.
_TILES = 'class Tiles:\n    HEADER = "/assets/earningsnerd-appicon.png"\n'
# (what, the files under app/ the case writes, "flag" or "pass" or "gap"): a string is app/form.py.
# An unregistered path is spelled with a name no image will take (earningsnerd-new, -unregistered).
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
    ("a registered constant handed to a function", _T + 'P = str(PurePosixPath(_T).with_name("earningsnerd-unregistered.png"))', "flag"),
    ("a directory taken from a registered constant", _T + "ASSETS = posixpath.dirname(_T)", "flag"),
    ("a registered constant cut by a format spec", _T + 'P = f"{base}{_T:.20}"', "flag"),
    ("a registered constant bound again", _T + '_T = "/assets/earningsnerd-new.png"', "flag"),
    ("a registered constant added to in place", _T + '_T += "@2x.png"', "flag"),
    ("a registered constant as a loop's variable", _T + "for _T in variants:\n    pass", "flag"),
    ("a registered constant rebound through global", _T + "def dark():\n    global _T\n    _T = variant()", "flag"),
    ("a registered path rebound through nonlocal", 'def outer():\n    t = "/assets/earningsnerd-appicon.png"\n\n    def dark():\n        nonlocal t\n        t = variant()\n\n    return dark', "flag"),
    ("a registered constant rebound by an except's name", _T + "try:\n    pass\nexcept Exception as _T:\n    pass", "flag"),
    ("a registered constant rebound by an import", _T + "from os import sep as _T", "flag"),
    ("a registered constant set from another module", {"a.py": _T, "b.py": "from app import a\na._T = variant()"}, "flag"),
    ("a registered path rebound through nonlocal two functions out", 'def a():\n    t = "/assets/earningsnerd-appicon.png"\n\n    def b():\n        def c():\n            nonlocal t\n            t = variant()\n\n        return c\n\n    return b', "flag"),
    ("a registered constant rebound by a walrus in a comprehension", _T + "P = [(_T := v) for v in vs]", "flag"),
    ("a registered constant rebound by a def", _T + "def _T():\n    pass", "flag"),
    ("a registered constant rebound by a class", _T + "class _T:\n    pass", "flag"),
    ("a registered constant rebound by a match's capture", _T + "match x:\n    case _T:\n        pass", "flag"),
    ("a registered constant as a parameter's default, which the scope around evaluates", _T + 'def f(_T=_T):\n    return _T.replace("appicon", "x")', "flag"),
    ("a registered constant as a lambda's default", _T + "F = lambda _T=_T: _T[:-4]", "flag"),
    ("a registered constant as a comprehension's first iterable, beside a variable of its name", _T + "P = [_T.upper() for _T in _T]", "flag"),
    ("a re-indented template returned", 'import textwrap\n\n\ndef f():\n    return textwrap.dedent(\'<img src="{base}/assets/earningsnerd-appicon.png">\')', "flag"),
    ("a re-indented template handed to a function", 'import textwrap\nIMG = textwrap.dedent(\'<img src="{base}/assets/earningsnerd-appicon.png">\')\nP = _helper(IMG)', "flag"),
    ("a registered constant rebound through global past a function that binds the name", _T + "def a():\n    _T = name\n\n    def b():\n        global _T\n        _T = variant()\n\n    return b", "flag"),
    ("a registered constant rebound by an import through global", _T + "def f():\n    global _T\n    from os import sep as _T", "flag"),
    ("a registered constant rebound by a plain import", _T + "import os as _T", "flag"),
    ("a registered constant deleted from another module", {"a.py": _T, "b.py": "from app import a\ndel a._T"}, "flag"),
    ("a registered constant deleted", _T + "del _T", "flag"),
    ("a registered constant changed after a class in a function binds its name", _T + 'def build():\n    class Variant:\n        _T = "dark"\n\n    return _T.replace("appicon", "x")', "flag"),
    ("a class's registered constant rebound through self", 'class Mail:\n    TILE = "/assets/earningsnerd-appicon.png"\n\n    def dark(self):\n        self.TILE = variant()', "flag"),
    ("a class's registered constant rebound in its body", 'class Mail:\n    TILE = "/assets/earningsnerd-appicon.png"\n    TILE = variant()', "flag"),
    ("a class's registered constant changed in its own body", 'class Mail:\n    TILE = "/assets/earningsnerd-appicon.png"\n    RETINA = TILE.replace(".png", "@2x.png")', "flag"),
    ("a class's registered constant changed through self, beside a module constant of its name", _T + 'class Mail:\n    _T = "/assets/earningsnerd-mark-sage.png"\n\n    def f(self):\n        return self._T.replace("sage", "x")', "flag"),
    ("a helper that takes textwrap.dedent's name", 'def dedent(s):\n    return s.replace("appicon", "x")\n\nP = dedent("/assets/earningsnerd-appicon.png")', "flag"),
    ("a re-indented template with a field after a registered path", 'import textwrap\nP = textwrap.dedent("<img src=\\"{base}/assets/earningsnerd-appicon.png{suffix}\\">")', "flag"),
    ("a registered constant aliased", _T + "TILE = _T", "flag"),
    ("a registered constant imported and changed", {"a.py": _T, "b.py": 'from app.a import _T\nP = _T + "@2x.png"'}, "flag"),
    ("a registered constant imported under another name", {"a.py": _T, "b.py": 'from app.a import _T as TILE\nP = TILE.replace("appicon", "x")'}, "flag"),
    ("a registered constant read through its module", {"a.py": _T, "b.py": "from app import a\nP = a._T[:-4]"}, "flag"),
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
    # A name bound through global or nonlocal, a class's attributes through its bases, an instance, another module.
    ("a name a global binds to a registered path's address, changed in another function", '_TILE_URL = None\n\n\ndef _init():\n    global _TILE_URL\n    _TILE_URL = f"{settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"\n\n\ndef retina():\n    return _TILE_URL.replace(".png", "@2x.png")\n', 'flag'),
    ('a registered path a global binds, sliced in the module', '_T = None\n\n\ndef _init():\n    global _T\n    _T = "/assets/earningsnerd-appicon.png"\n\n\nP = _T[:-4]\n', 'flag'),
    ('a registered path a nonlocal binds, changed in the function around', 'def outer():\n    t = None\n\n    def inner():\n        nonlocal t\n        t = "/assets/earningsnerd-appicon.png"\n\n    inner()\n    return t.replace("appicon", "x")\n', 'flag'),
    ("a registered path a class's body binds through global, bound again there", _T + 'class Mail:\n    global _T\n    _T = variant()\n', 'flag'),
    ("a registered path a class's body binds through global, changed in the body", 'class Mail:\n    global _U\n    _U = "/assets/earningsnerd-appicon.png"\n    P = _U[:-4]\n', 'flag'),
    ("a class's attribute read from another module that imports the class", {'a.py': _TILES, 'b.py': 'from app.a import Tiles\nP = Tiles.HEADER.replace("appicon", "x")\n'}, 'flag'),
    ("a class's attribute read through the module that holds the class", {'a.py': _TILES, 'b.py': 'from app import a\nP = a.Tiles.HEADER[:-4]\n'}, 'flag'),
    ("a class's attribute set from another module", {'a.py': _TILES, 'b.py': 'from app.a import Tiles\nTiles.HEADER = variant()\n'}, 'flag'),
    ("a base's attribute read through a subclass's self", _TILES + '\n\nclass Dark(Tiles):\n    def url(self):\n        return self.HEADER.replace("appicon", "x")\n', 'flag'),
    ("a base's attribute read through a subclass's name", _TILES + '\n\nclass Dark(Tiles):\n    pass\n\n\nP = Dark.HEADER.replace("appicon", "x")\n', 'flag'),
    ("a base's attribute read through a subclass in another module", {'a.py': _TILES, 'b.py': 'from app.a import Tiles\n\n\nclass Dark(Tiles):\n    def url(self):\n        return self.HEADER.replace("appicon", "x")\n'}, 'flag'),
    ("a base's attribute read from a third module through the subclass", {'a.py': _TILES, 'b.py': 'from app.a import Tiles\n\n\nclass Dark(Tiles):\n    pass\n', 'c.py': 'from app.b import Dark\nP = Dark.HEADER.replace("appicon", "x")\n'}, 'flag'),
    ("a class's attribute read through an instance", _TILES + '\n\nP = Tiles().HEADER.replace("appicon", "x")\n', 'flag'),
    ("a class's attribute read through type(self)", _TILES + '\n    def url(self):\n        return type(self).HEADER.replace("appicon", "x")\n', 'flag'),
    ("a class's attribute read through cls, changed", 'class Mail:\n    TILE = "/assets/earningsnerd-appicon.png"\n\n    @classmethod\n    def retina(cls):\n        return cls.TILE.replace(".png", "@2x.png")\n', 'flag'),
    ("an enum member's value added to in another module", {'a.py': 'import enum\n\n\nclass Tile(str, enum.Enum):\n    HEADER = "/assets/earningsnerd-appicon.png"\n', 'b.py': 'from app.a import Tile\nP = Tile.HEADER.value + "@2x"\n'}, 'flag'),
    ("a class's body that imports a registered path, changed through self", {'a.py': _T, 'b.py': 'class Mail:\n    from app.a import _T\n\n    def dark(self):\n        return self._T.replace("appicon", "x")\n'}, 'flag'),
    ('a decorator that changes a registered path, over a function whose parameter shares its name', _T + '\n\n@deco(_T.replace("appicon", "x"))\ndef f(_T):\n    return _T\n', 'flag'),
    ('an annotation that changes a registered path, on a parameter that shares its name', _T + '\n\ndef f(_T: _T.replace("appicon", "x")):\n    return 1\n', 'flag'),
    ("a class's body that reads a module's registered path before it binds the name", _T + '\n\nclass C:\n    Y = _T.replace("appicon", "x")\n    _T = "x"\n', 'flag'),
    ("a class's body that binds a registered path's name to a change of it", _T + '\n\nclass C:\n    _T = _T.replace("appicon", "x")\n', 'flag'),
    ("a nested class's decorator that changes its outer class's attribute", _TILES + '\n    @deco(HEADER.replace("appicon", "x"))\n    class Dark:\n        pass\n', 'flag'),
    ('a template re-indented from a name, handed to a function', 'import textwrap\n\nT = \'<img src="{base}/assets/earningsnerd-appicon.png">\'\nP = _helper(textwrap.dedent(T))\n', 'flag'),
    ('a template re-indented from a name, returned', 'import textwrap\n\nT = \'<img src="{base}/assets/earningsnerd-appicon.png">\'\n\n\ndef img():\n    IMG = textwrap.dedent(T)\n    return IMG\n', 'flag'),
    ('a template re-indented twice, handed to a function', 'import textwrap\n\nP = _helper(textwrap.dedent(textwrap.dedent(\'<img src="{base}/assets/earningsnerd-appicon.png">\')))\n', 'flag'),
    ('a registered path stripped of whitespace, returned', _T + '\n\ndef tile():\n    return _T.strip()\n', 'flag'),
    ('literals joined with + into a template, handed to a function', 'P = _helper(\'<img src="{base}\' + \'/assets/earningsnerd-appicon.png">\')\n', 'flag'),
    ('literals joined with + into a template, re-indented and handed to a function', 'import textwrap\n\nP = _helper(textwrap.dedent(\'<img src="{base}\' + \'/assets/earningsnerd-appicon.png">\'))\n', 'flag'),
    ('an f-string with no fields, a template handed to a function', 'P = _helper(f\'<img src="{{base}}/assets/earningsnerd-appicon.png">\')\n', 'flag'),
    ("a registered path a class's body binds through nonlocal, bound again there", 'def outer():\n    t = "/assets/earningsnerd-appicon.png"\n\n    class C:\n        nonlocal t\n        t = variant()\n\n    return C\n', 'flag'),
    ("a class's attribute changed through the class's name", _TILES + '\n\nP = Tiles.HEADER.replace("appicon", "x")\n', 'flag'),
    ("a class's attribute deleted through the class's name", _TILES + '\n\ndel Tiles.HEADER\n', 'flag'),
    ("a match mapping's rest that binds a registered path's name again", _T + 'match data:\n    case {**_T}:\n        pass\n', 'flag'),
    ("a nonlocal through a function that declares it nonlocal too, binding a registered path's name again", 'def a():\n    t = "/assets/earningsnerd-appicon.png"\n\n    def b():\n        nonlocal t\n\n        def c():\n            nonlocal t\n            t = variant()\n\n        c()\n\n    b()\n', 'flag'),
    # A string with nothing in front of a registered path is the path, and an address is changed however it is read.
    ("a registered constant in an f-string with nothing before it, handed to a function", _T + 'P = _img(f"{_T}")', "flag"),
    ("a registered constant after an empty string, in a container", _T + 'P = ["" + _T]', "flag"),
    ("an address aliased, then changed", 'U = f"{base}/assets/earningsnerd-appicon.png"\nV = U\nP = V.replace("appicon", "x")', "flag"),
    ("an address added to in place", 'U = f"{base}/assets/earningsnerd-appicon.png"\nU += "@2x.png"', "flag"),
    ("an address converted in an f-string", 'U = f"{base}/assets/earningsnerd-appicon.png"\nP = f"{U!s}@2x.png"', "flag"),
    ("an address cut by a format spec", 'U = f"{base}/assets/earningsnerd-appicon.png"\nP = f"{U:.40}"', "flag"),
    ("a binding the walk reaches after the one that reads it", 'try:\n    _T = "/assets/earningsnerd-appicon.png"\nexcept ImportError:\n    pass\nU = f"{base}{_T}"\nP = U.replace("appicon", "x")', "flag"),
    ("a registered constant bound in a block, imported and changed", {"a.py": 'if True:\n    _T = "/assets/earningsnerd-appicon.png"\n', "b.py": 'from app.a import _T\nP = _T + "@2x.png"'}, "flag"),
    ("a registered path in a setting the environment can replace", 'class Settings(BaseSettings):\n    MAIL_TILE: str = "/assets/earningsnerd-appicon.png"', "flag"),
    ("an address imported from another module, then changed", {"a.py": 'U = f"{base}/assets/earningsnerd-appicon.png"\n', "b.py": 'from app.a import U\nP = U.replace("appicon", "x")'}, "flag"),
    ("a registered path built in an f-string, imported and changed", {"a.py": _T + 'U = f"{_T}"\n', "b.py": 'from .a import U\nP = U + "@2x.png"'}, "flag"),
    ("a registered path concatenated from two strings, imported and changed", {"a.py": 'TILE = "/assets/" + "earningsnerd-appicon.png"\n', "b.py": 'from app.a import TILE\nP = TILE.replace("appicon", "x")'}, "flag"),
    ("a bare path imported where another module exports an address of the same name", {"a.py": _T + 'U = f"{_T}"\n', "b.py": 'from app.a import U\nP = [U]', "c.py": 'U = f"{base}/assets/earningsnerd-appicon.png"\n'}, "flag"),
    ("a registered path imported through a second module, then changed", {"a.py": _T, "b.py": 'from app.a import _T\nU = f"{_T}"\n', "c.py": 'from app.b import U\nP = U[:-4]'}, "flag"),
    ("an address filled by .format, then changed", 'IMG = \'<img src="{base}/assets/earningsnerd-appicon.png">\'\nP = IMG.format(base=b).replace("appicon", "x")', "flag"),
    ("an address filled by %, then sliced", 'P = ("%s/assets/earningsnerd-appicon.png" % base)[:-4]', "flag"),
    ("an address filled by %, then added to", 'P = "%s/assets/earningsnerd-appicon.png" % base + "@2x.png"', "flag"),
    ("an address stripped of characters", 'U = f"{base}/assets/earningsnerd-appicon.png"\nP = U.rstrip(".png")', "flag"),
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
    ("FRONTEND_URL stripped of whitespace alone", 'P = f"{settings.FRONTEND_URL.strip()}/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL converted to a string", 'P = str(settings.FRONTEND_URL) + "/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL read through !s", 'P = f"{settings.FRONTEND_URL!s}/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL read through :s", 'P = f"{settings.FRONTEND_URL:s}/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL in a conditional", 'P = f"{settings.FRONTEND_URL if light else DARK}/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL in an or", 'P = (settings.FRONTEND_URL or ORIGIN) + "/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL as an or's fallback", 'P = f"{settings.MAIL_ORIGIN or settings.FRONTEND_URL}/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL in a conditional's else", 'P = f"{DARK if dark else settings.FRONTEND_URL}/assets/earningsnerd-appicon.png"', "flag"),
    ("an address encoded, then changed", 'U = f"{base}/assets/earningsnerd-appicon.png"\nP = U.encode()[:-4]', "flag"),
    ("FRONTEND_URL last in an and", 'P = (ready and settings.FRONTEND_URL) + "/assets/earningsnerd-appicon.png"', "flag"),
    ("an address with a character replaced", 'U = f"{base}/assets/earningsnerd-appicon.png"\nP = U.replace("-", "_")', "flag"),
    ("FRONTEND_URL rstripped of whitespace alone", 'P = f"{settings.FRONTEND_URL.rstrip()}/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL rstripped of characters that leave its slash", 'P = f"{settings.FRONTEND_URL.rstrip(\' \')}/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL with a doubled slash removed", 'P = f"{settings.FRONTEND_URL.removesuffix(\'//\')}/assets/earningsnerd-appicon.png"', "flag"),
    ("FRONTEND_URL with a suffix removed that is not its slash", 'P = f"{settings.FRONTEND_URL.removesuffix(\'io/\')}/assets/earningsnerd-appicon.png"', "flag"),
    ("a site origin with a port", 'P = "https://www.earningsnerd.io:443/assets/earningsnerd-appicon.png"', "flag"),
    # What a client reads into the path, and where only a route's own path is exempt.
    ("a query written without its question mark", 'P = "/assets/earningsnerd-appicon.png&v=2"', "flag"),
    ("an escaped ampersand after a registered path", 'P = "<img src=\\"/assets/earningsnerd-appicon.png&amp;v=2\\">"', "flag"),
    ("an unregistered path in a route decorator's other argument", '@router.get("/api/x", summary="/assets/earningsnerd-new.png")\nasync def x(): ...', "flag"),
    ("an unregistered path in a decorator that is no route's", '@cache.memoize("/assets/earningsnerd-new.png")\ndef f(): ...', "flag"),
    ("an unregistered path in a route's body", '@router.get("/api/x")\nasync def x():\n    return "/assets/earningsnerd-new.png"', "flag"),
    # A placeholder host, or a placeholder token, in front of the path.
    ("an unregistered path after a host filled in by .format", 'P = "https://{host}/assets/earningsnerd-unregistered.png".format(host=h)', "flag"),
    ("an unregistered path after a host filled in by %", 'P = "https://%s/icons/icon-192.png" % h', "flag"),
    ("an unregistered path after a Template host", 'P = Template("https://$host/assets/earningsnerd-unregistered.png")', "flag"),
    ("an unregistered path after a Jinja host", {"templates/mail/host.html": '<img src="https://{{host}}/assets/earningsnerd-unregistered.png">'}, "flag"),
    ("an unregistered path after a protocol-relative filled-in host", 'P = "//{host}/icons/icon-192.png"', "flag"),
    ("an unregistered path after a %-token", 'P = "%BASE%/assets/earningsnerd-new.png"', "flag"),
    ("an unregistered path after an @-token", 'P = "@BASE@/assets/earningsnerd-new.png"', "flag"),
    ("an unregistered path after a dunder token", 'P = "__BASE__/assets/earningsnerd-new.png"', "flag"),
    ("an unregistered path after a %(name)s placeholder", 'P = "%(base)s/assets/earningsnerd-new.png" % m', "flag"),
    ("an unregistered path after a %r placeholder", 'P = "%r/assets/earningsnerd-new.png" % m', "flag"),
    # Every file the walk lists is read whole.
    ("an unregistered path in a JSON file", {"data/mail.json": '{"tile": "/assets/earningsnerd-new.png"}'}, "flag"),
    ("an unregistered path in a text file", {"data/copy.txt": "Our tile lives at /assets/earningsnerd-new.png"}, "flag"),
    ("an unregistered path in a router", {"routers/mail.py": 'P = "/assets/earningsnerd-new.png"'}, "flag"),
    ("an unregistered path in a binary file under app/assets", {"assets/fonts/planted.woff2": b"wOF2\x00\x01 /assets/earningsnerd-new.png\x00\xff"}, "flag"),
    ("an unregistered path past a module's first 4 KB", {"services/long.py": "X = 1\n" * 1000 + 'P = "/assets/earningsnerd-new.png"'}, "flag"),
    ("an unregistered path past a template's first 4 KB", {"templates/mail/long.html": "<p></p>\n" * 1000 + '<img src="/assets/earningsnerd-new.png">'}, "flag"),
    # Look-alikes that must pass.
    ("a registered path on FRONTEND_URL", 'P = f"{settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"', "pass"),
    ("a registered constant read whole on FRONTEND_URL", _T + 'P = f"{settings.FRONTEND_URL.rstrip(\'/\')}{_T}"', "pass"),
    ("a registered constant concatenated on FRONTEND_URL", _T + 'P = settings.FRONTEND_URL.rstrip("/") + _T', "pass"),
    ("a registered constant with a query after it", _T + 'P = f"{base}{_T}?v=2"', "pass"),
    ("a registered constant imported and read whole", {"a.py": _T, "b.py": 'from app.a import _T\nP = f"{base}{_T}"'}, "pass"),
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
    ("a registered path between escaped quotes", 'P = "src=&quot;/assets/earningsnerd-appicon.png&quot;"', "pass"),
    ("FRONTEND_URL stripped by removesuffix", 'P = f"{settings.FRONTEND_URL.removesuffix(\'/\')}/assets/earningsnerd-appicon.png"', "pass"),
    ("an address aliased, read whole", 'U = f"{base}/assets/earningsnerd-appicon.png"\nV = U\nP = f"<img src=\\"{V}\\">"', "pass"),
    ("an address bound again to another address", 'U = f"{base}/assets/earningsnerd-appicon.png"\nif dark:\n    U = f"{base}/assets/earningsnerd-mark-sage.png"', "pass"),
    ("a setting that holds no path", 'class Settings(BaseSettings):\n    FRONTEND_URL: str = "https://www.earningsnerd.io"', "pass"),
    ("a registered path in a class that is no setting", 'class Mail:\n    TILE = "/assets/earningsnerd-appicon.png"', "pass"),
    ("a registered constant read through !s", _T + 'P = f"{base}{_T!s}"', "pass"),
    ("a registered constant read through :s", _T + 'P = f"{base}{_T:s}"', "pass"),
    ("FRONTEND_URL stripped of its slash and whitespace", 'P = f"{settings.FRONTEND_URL.rstrip(\'/ \')}/assets/earningsnerd-appicon.png"', "pass"),
    ("FRONTEND_URL stripped of its slash at both ends", 'P = f"{settings.FRONTEND_URL.strip(\'/\')}/assets/earningsnerd-appicon.png"', "pass"),
    ("FRONTEND_URL stripped after an and", 'P = f"{settings.FRONTEND_URL and settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"', "pass"),
    ("a page with its line breaks replaced", 'page = f\'<img src="{base}/assets/earningsnerd-appicon.png">\'\nP = page.replace("\\n", "")', "pass"),
    ("FRONTEND_URL stripped in each value of a conditional", 'P = f"{settings.FRONTEND_URL.rstrip(\'/\') if light else DARK}/assets/earningsnerd-appicon.png"', "pass"),
    ("an address grown in place as a page", 'page = f\'<img src="{base}/assets/earningsnerd-appicon.png">\'\npage += "<p>Body</p>"', "pass"),
    ("an address logged through !r", 'U = f"{base}/assets/earningsnerd-appicon.png"\nlog(f"tile {U!r}")', "pass"),
    ("an address read by startswith", 'U = f"{base}/assets/earningsnerd-appicon.png"\nok = U.startswith("https://")', "pass"),
    ("a page stripped of whitespace", 'page = f\'<img src="{base}/assets/earningsnerd-appicon.png">\'\nP = page.strip()', "pass"),
    ("an attribute that shares an exported name, on an object no module binds", {"a.py": 'class HeaderTile:\n    url = f"{settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"\n', "b.py": "def path(request):\n    return request.url.path"}, "pass"),
    ("an attribute that shares a module's exported name, on an object no module binds", {"a.py": 'url = f"{settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"\n', "b.py": "def path(request):\n    return request.url.path"}, "pass"),
    ("an imported name its module binds to no path, beside a class attribute of that name on one", {"a.py": 'class Mail:\n    TILE = "/assets/earningsnerd-appicon.png"\n\n\nTILE = "dark"\n', "b.py": 'from app.a import TILE\nP = TILE.replace("appicon", "x")'}, "pass"),
    ("a method's bare name, its module's, beside a class attribute of that name on a registered path", '_T = "x"\n\n\nclass Mail:\n    _T = "/assets/earningsnerd-appicon.png"\n\n    def f(self):\n        return _T.upper()', "pass"),
    ("a name imported from another module than the one that exports it", {"a.py": _T, "b.py": "from app.layout import _T\nP = [_T]"}, "pass"),
    ("a dataclass field on a registered path, and an unrelated .path read elsewhere", {"a.py": '@dataclass\nclass Tile:\n    path: str = "/assets/earningsnerd-appicon.png"\n', "b.py": "def path_of(link):\n    return urlsplit(link).path.startswith('/api/')"}, "pass"),
    ("an address imported and read whole", {"a.py": 'U = f"{base}/assets/earningsnerd-appicon.png"\n', "b.py": 'from app.a import U\nP = f"<img src=\\"{U}\\">"'}, "pass"),
    ("a parameter named like a registered constant", _T + "def f(_T):\n    return _T.upper()", "pass"),
    ("a local named like a registered constant", _T + "def f():\n    _T = name\n    return _T.upper()", "pass"),
    ("a comprehension's variable named like a registered constant", _T + "P = [_T.upper() for _T in names]", "pass"),
    ("a registered constant compared", _T + "ok = path == _T", "pass"),
    ("a registered path compared", 'ok = path == "/assets/earningsnerd-appicon.png"', "pass"),
    ("a template inspect.cleandoc re-indents, filled later", 'import inspect\nIMG = inspect.cleandoc(\'<img src="{base}/assets/earningsnerd-appicon.png">\')\nP = IMG.format(base=b)', "pass"),
    ("an import in a function named like a registered constant", _T + "def f():\n    from os import sep as _T\n    return _T.upper()", "pass"),
    ("an except's name in a function named like a registered constant", _T + "def f():\n    try:\n        pass\n    except Exception as _T:\n        return _T.args", "pass"),
    ("textwrap.dedent imported under another name", 'from textwrap import dedent as dd\nIMG = dd("<img src=\\"{base}/assets/earningsnerd-appicon.png\\">")\nP = IMG.format(base=b)', "pass"),
    ("a def in a function named like a registered constant", _T + "def f():\n    def _T():\n        pass\n\n    return _T.__name__", "pass"),
    ("a generator's variable named like a registered constant", _T + "P = list(_T.upper() for _T in names)", "pass"),
    ("a set comprehension's variable named like a registered constant", _T + "P = {_T.upper() for _T in names}", "pass"),
    ("a dict comprehension's variable named like a registered constant", _T + "P = {_T: _T.upper() for _T in names}", "pass"),
    ("a positional-only parameter named like a registered constant", _T + "def f(_T, /):\n    return _T.upper()", "pass"),
    ("a keyword-only parameter named like a registered constant", _T + "def f(*, _T):\n    return _T.upper()", "pass"),
    ("a variadic parameter named like a registered constant", _T + "def f(*_T):\n    return _T[0]", "pass"),
    ("a keyword-variadic parameter named like a registered constant", _T + "def f(**_T):\n    return _T.items()", "pass"),
    ("a loop's variable in a function named like a registered constant", _T + "def f():\n    for _T in names:\n        return _T.upper()", "pass"),
    ("a class attribute named like a registered constant", _T + "class C:\n    _T = 1", "pass"),
    ("an instance attribute named like a registered constant", _T + "class C:\n    def f(self):\n        self._T = 1\n        return self._T + 1", "pass"),
    ("a method named like a registered constant", _T + "class C:\n    def _T(self):\n        return 1", "pass"),
    ("a registered constant compared against a tuple", _T + "ok = path in (_T, other)", "pass"),
    ("a registered path compared against a set", 'ok = path not in {"/assets/earningsnerd-appicon.png"}', "pass"),
    ("a registered path matched by a case", 'match path:\n    case "/assets/earningsnerd-appicon.png":\n        ok = True', "pass"),
    ("a re-indented template filled later", 'import textwrap\nIMG = textwrap.dedent(\"\"\"\n    <img src="{base}/assets/earningsnerd-appicon.png">\n\"\"\")\nP = IMG.format(base=b)', "pass"),
    ("a class's body that binds a module path's name to another value, then reads it", _T + '\n\nclass C:\n    _T = "x"\n    Y = _T.replace("x", "y")\n', 'pass'),
    ('literals joined with + into a template, filled where it is built', 'P = (\'<img src="{base}\' + \'/assets/earningsnerd-appicon.png">\').format(base=b)\n', 'pass'),
    ("a subclass's own attribute that shares its base's name", _TILES + '\n\nclass Text(Tiles):\n    HEADER = "x"\n\n    def url(self):\n        return self.HEADER.replace("x", "y")\n', 'pass'),
    ('a template re-indented, stripped of whitespace, then filled', 'import textwrap\n\nIMG = textwrap.dedent("""\n    <img src="{base}/assets/earningsnerd-appicon.png">\n""").strip()\nP = IMG.format(base=b)\n', 'pass'),
    ('a registered path compared against a nested tuple', _T + 'ok = p in (("a", _T), ("b", "c"))\n', 'pass'),
    ('a registered path in a frozenset a comparison holds', _T + 'ok = p in frozenset({_T, "x"})\n', 'pass'),
    ("a registered path as a dict's key a comparison holds", _T + 'ok = p in {_T: 1}\n', 'pass'),
    ('a registered path a match compares with its cases', _T + 'match _T:\n    case "x":\n        pass\n', 'pass'),
    ('an address a global binds, handed on whole', '_TILE_URL = None\n\n\ndef _init():\n    global _TILE_URL\n    _TILE_URL = f"{settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"\n\n\ndef url():\n    return _TILE_URL\n', 'pass'),
    ("a class's attribute read from another module and used whole", {'a.py': 'class Tiles:\n    HEADER = f"{settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"\n', 'b.py': 'from app.a import Tiles\nP = f"<img src=\\"{Tiles.HEADER}\\">"\n'}, 'pass'),
    ("a comprehension's walrus that binds the function's own name", _T + '\n\ndef f(names):\n    [(_T := n) for n in names]\n    return _T.upper()\n', 'pass'),
    # Out of the scan's reach: the header names each, and the rendered gate checks what each puts in mail.
    ("no slash before the path", 'P = urljoin(base + "/", "assets/earningsnerd-new.png")', "gap"),
    ("a path after a bare word", 'P = "BASE_URL/assets/earningsnerd-new.png"', "gap"),
    ("a path spelled with a dot segment or a percent-escape", 'P = "/./assets/earningsnerd-new.png"', "gap"),
    ("a registered path followed by a character the scan reads as its end", 'P = "/assets/earningsnerd-appicon.png,2x"', "gap"),
    ("a JSON file's escaped slashes", {"data/mail.json": '{"tile": "\\/assets\\/earningsnerd-new.png"}'}, "gap"),
    ("a data file's path, changed by the code that reads it", {"data/mail.json": '{"tile": "/assets/earningsnerd-appicon.png"}', "form.py": 'P = TILES["tile"][:-4] + "@2x.png"'}, "gap"),
    ("a registered path on another origin's variable", 'P = f"{settings.CORS_ORIGINS[0]}/assets/earningsnerd-appicon.png"', "gap"),
    ("a registered path after another origin filled in as a host", 'P = "https://{host}/assets/earningsnerd-appicon.png".format(host=h)', "gap"),
    ("FRONTEND_URL read through a name, a call or a conversion that quotes it", 'base = settings.FRONTEND_URL\nP = f"{base}/assets/earningsnerd-appicon.png"\n'
     'Q = f"{format(settings.FRONTEND_URL)}/assets/earningsnerd-appicon.png"\nR = f"{settings.FRONTEND_URL!r}/assets/earningsnerd-appicon.png"', "gap"),
    ("FRONTEND_URL filled into a template", 'P = \'<img src="{base}/assets/earningsnerd-appicon.png">\'.format(base=settings.FRONTEND_URL)', "gap"),
    ("an address a function hands back, changed by its caller", 'def u():\n    return f"{base}/assets/earningsnerd-appicon.png"\n\nP = u().replace("appicon", "x")', "gap"),
    ("an address handed to a function that changes it", 'def _retina(url):\n    return url.replace(".png", "@2x.png")\n\nU = f"{base}/assets/earningsnerd-appicon.png"\nP = _retina(U)', "gap"),
    ("an address held in a container, an attribute or a conditional, then changed", 'U = f"{base}/assets/earningsnerd-appicon.png"\n'
     'P = [U][0].replace("appicon", "x")\nQ = {"u": U}["u"].replace("appicon", "x")\nR = (U if dark else other).replace("appicon", "x")\n'
     'S = (u := f"{base}/assets/earningsnerd-appicon.png").replace("appicon", "x")\n\n\nclass Mail:\n    def __init__(self):\n'
     '        self.u = f"{base}/assets/earningsnerd-appicon.png"\n\n    def dark(self):\n        return self.u.replace("appicon", "x")', "gap"),
    ("an address filled into another template, with a suffix", 'U = f"{base}/assets/earningsnerd-appicon.png"\nP = "{}@2x.png".format(U)', "gap"),
    ("a name bound to a registered path, rebound where the scan does not look", {
        "a.py": _T + 'setattr(sys.modules[__name__], "_T", variant())\nglobals()["_T"] = variant()\nvars()["_T"] = variant()\n',
        "b.py": 'from app import a\na.__dict__["_T"] = variant()\n',
    }, "gap"),
    ("a name read through getattr or globals()", {"a.py": _T, "b.py": 'from app import a\nP = getattr(a, "_T").replace("appicon", "x")'}, "gap"),
    ("a Jinja filter applied to a path", {"templates/mail/tile.html": '{{ "/assets/earningsnerd-appicon.png" | replace("appicon", "x") }}'}, "gap"),
    ("a class's attribute read through an instance held in a name, or a class nested in another", 'class Mail:\n    class Tiles:\n        HEADER = "/assets/earningsnerd-appicon.png"\n\n\nP = Mail.Tiles.HEADER.replace("appicon", "x")\nm = Mail.Tiles()\nQ = m.HEADER.replace("appicon", "x")\n', 'gap'),
    ("a path the site serves from a route", 'P = "/manifest.webmanifest"', "gap"),
]
# One case for each character the header says a URL path can start after. The list is written here,
# not taken from _DELIMITERS, so narrowing that set fails a case.
FORMS += [(f"a path after {c!r}", f"P = {'x' + c + '/assets/earningsnerd-new.png'!r}", "flag") for c in " \t\r\n\"'`<>()[]=:,;}"]
# One case for each entity the scan reads as the end of a path, written out so narrowing _PATH fails a case.
FORMS += [
    (f"a registered path before {e}", f'P = "src=/assets/earningsnerd-appicon.png{e}"', "pass")
    for e in ("&quot;", "&apos;", "&lt;", "&gt;", "&#34;", "&#39;", "&#x22;", "&#x27;")
]


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
    whats = [what for what, _, _ in FORMS]
    assert len(set(whats)) == len(whats), "each planted form has a name of its own"
    gaps = sorted(what for what, _, outcome in FORMS if outcome == "gap")
    section = __doc__.split("planted as gaps, one case each:\n", 1)[1].split("\n\n", 1)[0]
    named = sorted(line[2:].split(": ", 1)[0] for line in section.splitlines() if line.startswith("- "))
    assert gaps == named, "the header names each gap a case marks, and a case marks each gap the header names: keep the two in step"
    outcomes = [outcome for _, _, outcome in FORMS]
    # Equalities, not floors, so a form dropped after one is added still fails (lessons/test-allowlist-caps-are-equalities.md).
    assert (outcomes.count("flag"), outcomes.count("pass")) == (196, 89), (
        "a planted form was added or dropped: keep these counts equal to FORMS in the same diff, and say why one goes"
    )


def test_the_scan_keeps_every_place_it_reads_a_registered_path(tmp_path):
    root = tmp_path / "app" / "services"
    root.mkdir(parents=True)
    (root / "email_service.py").write_text(_T + 'P = f"{base}{_T}"\n', encoding="utf-8")
    (root / "waitlist_service.py").write_text(_T, encoding="utf-8")
    places = _scan_app(root.parent)[1]["/assets/earningsnerd-appicon.png"]
    assert places == {"app/services/email_service.py:1", "app/services/email_service.py:2", "app/services/waitlist_service.py:1"}, (
        f"a second module's binding of a registered path hides the first's: {places}"
    )


def _length(path: Path) -> int:
    """How many characters a file holds, read without the walk's own reader."""
    raw = path.read_bytes()
    try:
        return len(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return len(raw)  # latin-1, which the walk falls back to, reads each byte as one character


def test_mail_addresses_the_site_only_by_registered_paths():
    assert {"assets", "icons"} <= set(SITE_NAMES), f"frontend/public no longer reads as the site's files: {SITE_NAMES}"
    found, registered, scanned = _scan_app()
    listing = {str(p.relative_to(BACKEND)): _length(p) for p in APP.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    unread = sorted(set(listing) ^ set(scanned)) + sorted(f for f in set(listing) & set(scanned) if listing[f] != scanned[f])
    assert not unread and len(scanned) > 200, f"the walk no longer reads every file in backend/app whole: {unread[:10]}"
    assert not found, (
        "these strings address a file of the site's other than by a whole registered path on FRONTEND_URL, used "
        "whole. Register a path mail shows in frontend/tests/unit/publishedAssetUrls.json in the same PR. Spell it "
        "whole where the address is built, on settings.FRONTEND_URL.rstrip('/'), and hand on the address, never the "
        "path: a registered path may sit in the f-string or the concatenation that builds an address, in a template "
        "that is filled, or in a name bound to it once and read only there (LOGO_README.md › Published URLs stay "
        "put). A string here that is no address mail carries narrows this gate by its shape, never by its name, with "
        "a planted case (lessons/arch-gate-reference-values-are-themselves-gated.md):\n" + "\n".join(found)
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
