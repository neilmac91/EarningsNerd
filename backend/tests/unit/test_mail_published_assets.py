"""Gate: mail addresses a file of the site's only by a registered path, built on FRONTEND_URL.

Sent mail keeps every address it carries for as long as the message is kept, and nobody can edit it
after sending, so a file of the site's that the backend puts in mail is published: its path must never
move or change (``frontend/public/assets/LOGO_README.md`` › Published URLs stay put). The register,
``frontend/tests/unit/publishedAssetUrls.json``, names the published paths and the origin mail
addresses them on, and ``frontend/tests/unit/publishedAssetUrls.spec.ts`` holds each path to its
file's bytes and keeps the middleware and every redirect and rewrite off it. This gate holds the
backend to the rule's mail half (CLAUDE.md rule 12). It reads every string in ``backend/app``: each
literal and f-string part of the Python, docstrings and the API's route paths aside, and every other
text file whole. In them:

- the path of a file the site serves from ``frontend/public``, or of one of its directories, where a
  URL path can start (the start of a string, after a quote, a bracket, "=", ":", ",", ";",
  whitespace, a placeholder such as ``{base}``, ``%s`` or ``$base``) spells a whole registered path.
  A directory left open for a name to follow (``"/assets/"``, ``"/assets"``,
  ``f"{base}/icons/{name}"``) fails, so a path composed at run time has to be written out whole;
- no origin of the site's (``earningsnerd.io`` or any host under it, with or without a scheme) and no
  second slash is spelled in front of such a path: mail builds it on ``FRONTEND_URL``, and a doubled
  slash answers 308;

and the header's tile follows ``FRONTEND_URL`` whatever it is set to, with a trailing slash stripped,
while ``FRONTEND_URL``'s default is the register's origin.

``FORMS`` plants a case for each way the rule can be broken and each look-alike that must pass, and
``test_the_scan_scores_every_planted_form`` scores them. Out of reach, and planted as gaps: a path
written with no slash before it (``"assets/x.png"`` joined to a base that ends in one), a registered
path joined at run time to an origin other than ``FRONTEND_URL`` (the scan reads the path, not what it
is joined to), and a path the site serves from a route rather than a file (``app/manifest.ts``).
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
# A placeholder a base is put in, ending right before the path: %s, %(base)s, $base.
_PLACEHOLDER_BEFORE = re.compile(r"(?:%(?:\(\w+\))?[sr]|\$\w+)$")
_DELIMITERS = set(" \t\r\n\"'`<>()[]=:,;}")
# Calls whose first argument is a route of the API, not an address mail carries.
_ROUTE_CALLS = {"get", "post", "put", "patch", "delete", "head", "options", "api_route", "route", "websocket"}


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
        origin = _ORIGIN_BEFORE.search(before)
        if origin and not _site_host(origin.group(1)):
            continue  # another site's file is not the site's to publish
        if origin or _SITE_HOST_BEFORE.search(before):
            found.append(f"{(origin or _SITE_HOST_BEFORE.search(before)).group(0).lstrip()}{path}: an origin of the site's in front of the path")
        elif before.endswith("/"):
            found.append(f"/{path}: a doubled slash in front of the path")
        elif before and before[-1] not in _DELIMITERS and not _PLACEHOLDER_BEFORE.search(before):
            continue  # a file path or a sub-path of another URL ("app/assets/", "/static/assets/")
        elif path in REGISTERED:
            registered.add(path)
        else:
            found.append(f"{path}: not a whole registered path")
    return found, registered


def _skipped(tree: ast.AST) -> set[int]:
    """The strings that are documentation (docstrings) or the API's own routes (``@router.get(...)``)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _ROUTE_CALLS:
            if node.args and isinstance(node.args[0], ast.Constant):
                ids.add(id(node.args[0]))
    return ids


def _scan_python(source: str, where: str) -> tuple[list[str], dict[str, str]]:
    tree = ast.parse(source)
    skip = _skipped(tree)
    found: list[str] = []
    registered: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)) and id(node) not in skip:
            text = node.value if isinstance(node.value, str) else node.value.decode("latin-1")
            bad, good = _scan(text)
            found += [f"{where}:{node.lineno}: {v}" for v in bad]
            registered.update((p, f"{where}:{node.lineno}") for p in good)
    return found, registered


def _scan_app() -> tuple[list[str], dict[str, str]]:
    found: list[str] = []
    registered: dict[str, str] = {}
    for path in sorted(p for p in APP.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        where = str(path.relative_to(BACKEND))
        if path.suffix == ".py":
            bad, good = _scan_python(path.read_text(encoding="utf-8"), where)
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue  # a binary file (a font, an image) holds no address
            bad, seen = _scan(text)
            bad, good = [f"{where}: {v}" for v in bad], {p: where for p in seen}
        found += bad
        registered.update(good)
    return found, registered


# (what, "py" or "text", source, outcome): "flag" breaks the rule, "pass" is a look-alike, "gap" breaks
# the rule out of the scan's reach (the header names each one).
FORMS = [
    ("a whole registered path", "py", 'P = "/assets/earningsnerd-appicon.png"', "pass"),
    ("an unregistered path", "py", 'P = "/assets/earningsnerd-new.png"', "flag"),
    ("a path in an attribute", "py", 'P = "<img src=\\"/assets/earningsnerd-new.png\\">"', "flag"),
    ("a name left open in an f-string", "py", 'f"{base}/assets/{name}.png"', "flag"),
    ("a directory concatenated with a name", "py", 'P = "/assets/" + name', "flag"),
    ("a directory constant", "py", 'ASSETS = "/assets"', "flag"),
    ("a join", "py", 'posixpath.join("/assets", name)', "flag"),
    ("a format template, the template's own spelling", "py", 'P = "<img src=\\"{base}/assets/earningsnerd-new.png\\">".format(base=b)', "flag"),
    ("a %-template", "py", 'P = "%s/assets/earningsnerd-new.png" % base', "flag"),
    ("a string.Template", "py", 'Template("$base/assets/earningsnerd-new.png")', "flag"),
    ("a Jinja template", "text", '<img src="{{ base }}/assets/earningsnerd-new.png">', "flag"),
    ("the second candidate of a srcset", "py", 'P = "/assets/earningsnerd-appicon.png 1x, /assets/earningsnerd-new@2x.png 2x"', "flag"),
    ("a path behind an escaped quote", "py", 'P = "src=&quot;/assets/earningsnerd-new.png&quot;"', "flag"),
    ("a CSS url()", "py", 'P = "background:url(/assets/earningsnerd-new.png)"', "flag"),
    ("a registered name with a suffix", "py", 'P = "/assets/earningsnerd-appicon.png;v=2"', "flag"),
    ("bytes", "py", 'P = b"/assets/earningsnerd-new.png"', "flag"),
    ("another directory the site serves", "py", 'P = "/icons/icon-192.png"', "flag"),
    ("a file at the site's root", "py", 'P = "/og-image.png"', "flag"),
    ("the apex in front of a registered path", "py", 'P = "https://earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("www in front of a registered path", "py", 'P = "https://www.earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("a protocol-relative origin", "py", 'P = "//www.earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("plain http in capitals", "py", 'P = "HTTP://WWW.EARNINGSNERD.IO/assets/earningsnerd-appicon.png"', "flag"),
    ("the site's host with no scheme", "py", 'P = "www.earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("the API's host", "py", 'P = "https://api.earningsnerd.io/assets/earningsnerd-appicon.png"', "flag"),
    ("a doubled slash after a base", "py", 'f"{base}//assets/earningsnerd-appicon.png"', "flag"),
    ("a registered path on FRONTEND_URL", "py", 'f"{settings.FRONTEND_URL.rstrip(\'/\')}/assets/earningsnerd-appicon.png"', "pass"),
    ("a registered path with a query", "py", 'P = "/assets/earningsnerd-appicon.png?v=2"', "pass"),
    ("a docstring", "py", 'def f():\n    """Shows /assets/earningsnerd-new.png."""', "pass"),
    ("a comment", "py", "# /assets/earningsnerd-new.png\nX = 1", "pass"),
    ("a route of the API", "py", '@router.get("/favicon.ico")\nasync def favicon(): ...', "pass"),
    ("the backend's own file path", "py", 'P = "app/assets/fonts/Inter-Variable-latin.woff2"', "pass"),
    ("the frontend's file path", "py", 'P = "frontend/public/assets/earningsnerd-new.png"', "pass"),
    ("another site's file", "py", 'P = "https://cdn.example.com/assets/earningsnerd-new.png"', "pass"),
    ("a sub-path of another URL", "py", 'P = "https://www.sec.gov/Archives/assets/x.htm"', "pass"),
    ("a directory's name in prose", "py", 'P = "current assets/liabilities"', "pass"),
    ("a longer name that starts like a directory", "py", 'P = "/assets-manifest.json"', "pass"),
    ("no slash before the path", "py", 'urljoin(base + "/", "assets/earningsnerd-new.png")', "gap"),
    ("a registered path on another origin's variable", "py", 'f"{settings.API_BASE_URL}/assets/earningsnerd-appicon.png"', "gap"),
    ("a path the site serves from a route", "py", 'P = "/manifest.webmanifest"', "gap"),
]


def test_the_scan_scores_every_planted_form():
    wrong = []
    for what, kind, source, outcome in FORMS:
        found = _scan_python(source, what)[0] if kind == "py" else _scan(source)[0]
        if bool(found) != (outcome == "flag"):
            wrong.append(f"{what}: expected {'flagged' if outcome == 'flag' else 'clean'}, got {found or 'clean'}")
    assert not wrong, "the scan no longer scores its planted forms:\n" + "\n".join(wrong)
    gaps = {what for what, _, _, outcome in FORMS if outcome == "gap"}
    assert gaps == {
        "no slash before the path",
        "a registered path on another origin's variable",
        "a path the site serves from a route",
    }, "the header names each gap the cases mark: keep the two in step"


def test_mail_addresses_the_site_only_by_registered_paths():
    assert {"assets", "icons"} <= set(SITE_NAMES), f"frontend/public no longer reads as the site's files: {SITE_NAMES}"
    found, registered = _scan_app()
    assert not found, (
        "these strings address a file of the site's other than by a whole registered path on FRONTEND_URL. "
        "Register a path mail shows in frontend/tests/unit/publishedAssetUrls.json in the same PR, spell it "
        "whole and build it on settings.FRONTEND_URL (LOGO_README.md › Published URLs stay put):\n"
        + "\n".join(found)
    )
    assert registered.get(email_service._HEADER_TILE_PATH, "").startswith("app/services/email_service.py:"), (
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
