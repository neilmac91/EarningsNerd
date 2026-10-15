"""Gate: every address the mail carries into the site's files is a registered path on FRONTEND_URL.

``test_mail_published_assets.py`` reads the code that builds mail, and cannot follow a value through it.
This gate reads the mail as it is sent, so an address is checked however the code derived it: a
``.replace``, an alias, a join, a fill, a helper, a rebinding (``frontend/public/assets/LOGO_README.md``
› Published URLs stay put).

It calls every public function of ``email_service``, the module that builds the mail, with inputs that
run every line of the module: a check holds them to it, so a branch they skip fails here until they take
it. It runs them in an interpreter of their own, with these settings:
- ``FRONTEND_URL`` is set to a sentinel that keeps its trailing slash, so an address built when the
  module loads is built on the sentinel too;
- the site's other origins (``CORS_ORIGINS_STR``) are set to hosts of their own.

It reads every string a function sends or returns. A page, as ``_wrap_html`` builds it, is read as its
markup; any other string (a plain-text copy, a subject) as markup and as the text it is, as
``_hidden_text`` sends it. In them it reads:
- each attribute that holds an address: ``srcset`` candidate by candidate, as HTML parses it; a
  ``<meta>`` tag's content; a relative address, resolved against a ``<base href>``;
- each URL in CSS, in a ``style`` attribute or a ``<style>`` block, with its escapes decoded: a ``url()``,
  a quoted string such as an ``image-set()``'s, an absolute URL;
- the markup inside Outlook's conditional comments;
- every absolute URL in the text, ``www.`` included, read across a comment or a ``<wbr>``.

An address into the site's files is one into a directory or a root file under ``frontend/public``, on
an origin of the site's or on none. It is resolved as a client resolves it: backslashes, dot segments,
percent-escapes, a host's trailing dot. Each such address must be a whole registered path
(``frontend/tests/unit/publishedAssetUrls.json``), spelled as registered, its query and fragment aside.
It must also be built on ``FRONTEND_URL`` with that slash stripped:
- on no other origin of the site's: ``earningsnerd.io`` or a host under it, another origin the settings
  set, or a loopback host, a setting's local default;
- never without an origin, since a mail has no base URL;
- never after a doubled slash, which answers 308.

The render list is held to ``email_service``'s public functions, and no other module in ``backend/app``
may reach its private names, so a new mail fails here until it is rendered. What it cannot see:
- which way a branch within one line goes (``x if c else y``, ``a or b``);
- the links a caller hands in, for which the inputs are stand-ins; the code scan reads the callers;
- what runs before the mail is built, elsewhere, such as a job rebinding a module's name;
- an origin of the site's that a setting the render leaves alone points at another site's host;
- a private name reached through ``getattr`` or ``importlib``;
- mail built or finished outside ``email_service``: ``routers/contact.py``'s confirmation (E56), the
  internal admin and team notices, and what a caller adds to a page before it sends it
  (``data_quality_service.run_and_email`` appends the report's text copy, as ``_hidden_text`` would).
"""
import ast
import html
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import CodeType
from urllib.parse import unquote, urljoin, urlsplit

import pytest

from app.services import email_service

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
APP = BACKEND / "app"
EMAIL_SERVICE = APP / "services" / "email_service.py"
PUBLIC = REPO / "frontend" / "public"
REGISTER = json.loads((REPO / "frontend" / "tests" / "unit" / "publishedAssetUrls.json").read_text(encoding="utf-8"))
REGISTERED = frozenset(entry["url"] for entry in REGISTER["paths"])
SITE_NAMES = frozenset(p.name for p in PUBLIC.iterdir() if not p.name.startswith("."))
SENTINEL = "https://frontend.example.test/"  # FRONTEND_URL with a trailing slash, which a value may keep
SENTINEL_HOST = urlsplit(SENTINEL).hostname
BUILT_ON = SENTINEL.rstrip("/") + "/"
TILE = f"{SENTINEL.rstrip('/')}/assets/earningsnerd-appicon.png"
# The site's other origins, as the render sets them: an address on one is on an origin of the site's.
OTHER_ORIGINS = ("https://cors-one.example.test", "https://cors-two.example.test")
OTHER_HOSTS = frozenset(urlsplit(origin).hostname for origin in OTHER_ORIGINS)
# A loopback host stands for one of the site's origins too: it is a setting's local default.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})

TO = "recipient@example.com"
LINK = "https://e.test/t"
WAITLIST = dict(name="Ada", position=3, referral_link=LINK, verification_link=LINK)
REFERRAL = dict(name="Ada", new_position=2, referral_link=LINK)
FILING = dict(name="Ada", company_name="Acme Corp", ticker="ACME", filing_type="10-K", filing_date="2026-01-01")
ALERTS = [
    dict(FILING, filing_id=1, wording_changes={"has_changes": True, "items_total": 3}),
    dict(FILING, filing_id=1, wording_changes={"has_changes": False, "items_total": 0}),
    dict(FILING, filing_id=1, wording_changes={"prior_reference_only": True, "items_total": 2}),
    dict(FILING, filing_url=LINK),
    FILING,
]
DIGEST_ITEM = {"company_name": "Acme Corp", "ticker": "ACME", "filing_type": "10-K", "filing_date": "2026-01-01"}
DIGEST = dict(name="Ada", items=[dict(DIGEST_ITEM, filing_id=1), dict(DIGEST_ITEM, filing_url=LINK), DIGEST_ITEM])
EARNINGS = [
    dict(name="Ada", items=[{"ticker": "ACME", "company_name": "Acme Corp", "time": "bmo"}, {"ticker": "BETA", "status": "reported"}]),
    dict(name="Ada", items=[{"ticker": "ACME", "company_name": "Acme Corp", "time": "amc"}]),
]
CLEAN_REPORT = {"ticker_mismatches": [], "ticker_not_in_file": [], "coverage_gaps": [], "filing_anomalies": [], "partial_reasons": []}
FULL_REPORT = {
    "ticker_mismatches": [{"ticker": "ACME", "primary": "ACMX", "cik": 1}],
    "ticker_not_in_file": [{"ticker": "GONE", "cik": 2}],
    "coverage_gaps": [{"ticker": "ACME", "concept": "Revenues", "last_fy": 2023, "last_total_assets_fy": 2025}],
    "filing_anomalies": [{"ticker": "ACME", "first_fact_fy": 2010, "last_fact_fy": 2025, "stored_10k_rows": 2}],
    "partial_reasons": [{"sic_prefix": "60", "reason": "no XBRL", "count": 3}],
    "universe_coverage": {"companies_with_summary": 10, "stub_companies": None},
    "job_health": [{"job": "filing_scan", "latest_status": "ok", "last_success": None, "stale": True}],
    "summary_audits": {"snapshot_population": 5, "families": {"figure_trace": {
        "recorded": 4, "unavailable": 1, "missing": 1, "malformed": 0, "flagged": 1, "flagged_pct": 25, "counts": {"would_snap": 2}}}},
    "weekly_readout": {"status": "complete", "reason": None, "dimensions": {"accuracy": 4.5}},
}

# Every public function of email_service that builds mail, with inputs that run every line of the module.
RENDERS = {
    "render_welcome_email": [WAITLIST],
    "send_waitlist_welcome_email": [dict(WAITLIST, to_email=TO)],
    "render_referral_success_email": [REFERRAL],
    "send_referral_success_email": [dict(REFERRAL, to_email=TO)],
    "send_verification_email": [dict(to_email=TO, name="Ada", verification_link=LINK)],
    "send_invite_email": [dict(to_email=TO, magic_link=LINK), dict(to_email=TO, magic_link=LINK, name="Ada")],
    "send_password_reset_email": [dict(to_email=TO, name="Ada", reset_link=LINK)],
    "send_oauth_linked_email": [dict(to_email=TO, name="Ada", provider="Google")],
    "send_account_exists_email": [dict(to_email=TO, name="Ada", login_link=LINK, reset_link=LINK)],
    "render_new_filing_alert": ALERTS,
    "build_new_filing_alert": ALERTS,
    "send_new_filing_alert": [dict(alert, to_email=TO) for alert in ALERTS],
    "render_daily_digest": [DIGEST],
    "build_daily_digest": [DIGEST],
    "send_daily_digest": [dict(DIGEST, to_email=TO)],
    "render_earnings_day_alert": EARNINGS,
    "send_earnings_day_alert": [dict(earnings, to_email=TO) for earnings in EARNINGS],
    "render_data_quality_report": [dict(report=CLEAN_REPORT), dict(report=FULL_REPORT)],
}
# The public functions that build no mail, and why.
NOT_MAIL = {"wording_changes_line": "a line of text the alert renderers set in their pages"}

_URL_ATTRIBUTES = {"src", "href", "background", "poster", "action", "formaction", "cite", "longdesc", "data", "xlink:href", "o:href"}
_ASCII_SPACE = " \t\n\r\f"
_CSS_ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6})[ \t\n\r\f]?|\\(.)", re.DOTALL)
_CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)""", re.IGNORECASE | re.DOTALL)
_CSS_STRING = re.compile(r"""(['"])(.*?)\1""", re.DOTALL)  # image-set('x.png' 1x) takes a bare string
_ABSOLUTE_URL = re.compile(r"""(?:https?:)?//[^\s"'<>()]+""", re.IGNORECASE)
_TEXT_URL = re.compile(r"""(?:(?:https?:)?//|\bwww\.)[^\s"'<>()]+""", re.IGNORECASE)  # a mail view links www. too
_PAGE = re.compile(r"\s*<!doctype html\b", re.IGNORECASE)  # the page _wrap_html builds


def _srcset(value: str) -> list[str]:
    """The candidates' addresses, as HTML parses a srcset: an address, then descriptors to a comma."""
    found, i = [], 0
    while i < len(value):
        while i < len(value) and (value[i] in _ASCII_SPACE or value[i] == ","):
            i += 1
        start = i
        while i < len(value) and value[i] not in _ASCII_SPACE:
            i += 1
        address = value[start:i]
        if address.endswith(","):
            found.append(address.rstrip(","))
            continue
        if address:
            found.append(address)
        in_parens = False  # a parenthesis does not nest: the first ")" closes it
        while i < len(value):
            character, i = value[i], i + 1
            if in_parens:
                in_parens = character != ")"
            elif character == "(":
                in_parens = True
            elif character == ",":
                break
    return found


def _css(text: str) -> list[str]:
    """The addresses in CSS, its escapes decoded: each url(), each quoted string (an image-set()'s), and
    every absolute URL."""
    text = _CSS_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)) if m.group(1) else m.group(2), text)
    found = [m.group(2).strip() for m in _CSS_URL.finditer(text)] + [m.group(2).strip() for m in _CSS_STRING.finditer(text)]
    return found + [m.group(0) for m in _ABSOLUTE_URL.finditer(text)]


class _Addresses(HTMLParser):
    """Every address a page carries, as a client reads it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []
        self.base: str | None = None
        self.text: list[str] = []  # the text since the last tag that breaks it

    def _flush(self) -> None:
        text, self.text = "".join(self.text), []
        urls = [m.group(0).rstrip(".,;:!?") for m in _TEXT_URL.finditer(text)]
        self.found += [f"//{url}" if url.lower().startswith("www.") else url for url in urls]

    def handle_starttag(self, tag, attrs):
        if tag != "wbr":
            self._flush()
        values = dict(attrs)
        if tag == "base" and values.get("href") and self.base is None:
            self.base = values["href"].strip()
        if tag == "meta" and values.get("content") and re.match(r"(?:https?:)?//|/", values["content"].strip(), re.IGNORECASE):
            self.found.append(values["content"].strip())
        for name, value in attrs:
            if value is None:
                continue
            if name == "srcset":
                self.found += _srcset(value)
            elif name in _URL_ATTRIBUTES:
                self.found.append(value.strip(_ASCII_SPACE))
            elif name == "style":
                self.found += _css(value)

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        self._flush()

    def handle_data(self, data):
        if self.lasttag == "style":
            self.found += _css(data)
        self.text.append(data)

    def handle_comment(self, data):
        # A comment is not shown, so the text runs on across it; Outlook's conditional comments hold
        # markup of their own, read as a page of its own.
        self.found += addresses(data)

    def close(self):
        super().close()
        self._flush()


def addresses(page: str) -> list[str]:
    """Every address in a page, a relative one resolved against the page's <base href>."""
    parser = _Addresses()
    parser.feed(page)
    parser.close()
    return [urljoin(parser.base, a) if parser.base and not urlsplit(a).scheme and not a.startswith("//") else a for a in parser.found]


def read(sent: str) -> list[str]:
    """Every address a string carries: a page's, read as its markup, and any other string's, read as markup
    and as the text it is, as _hidden_text sends it, so a plain-text copy's <https://...> is read too."""
    found = addresses(sent)
    return found if _PAGE.match(sent) else found + addresses(html.escape(sent))


def _resolved(path: str) -> str:
    """The path a client requests: percent-escapes decoded and dot segments removed (RFC 3986 § 5.2.4)."""
    out: list[str] = []
    segments = unquote(path).split("/")
    for i, segment in enumerate(segments):
        if segment == "..":
            if out and out != [""]:  # a parent segment never climbs above the root
                out.pop()
        elif segment != ".":
            out.append(segment)
        if segment in (".", "..") and i == len(segments) - 1:
            out.append("")
    return "/".join(out)


def problem(address: str) -> str | None:
    """What is wrong with an address into the site's files, or None when it is right or points elsewhere."""
    address = re.sub(r"[\t\n\r]", "", address.strip(_ASCII_SPACE)).replace("\\", "/")  # as a URL parser reads it
    parts = urlsplit(address)
    host = (parts.hostname or "").rstrip(".")
    site = (
        host in {SENTINEL_HOST, *OTHER_HOSTS, *LOOPBACK_HOSTS}
        or host.endswith(".localhost")
        or host == "earningsnerd.io"
        or host.endswith(".earningsnerd.io")
    )
    if (parts.netloc and not site) or parts.scheme.lower() not in ("", "http", "https"):
        return None  # another site's address, or mailto:, tel:, cid:
    if _resolved(parts.path).lstrip("/").split("/", 1)[0] not in SITE_NAMES:
        return None  # a page of the site's, not one of its files
    if not parts.netloc:
        return "has no origin, and a mail has no base URL: build it on FRONTEND_URL"
    if host != SENTINEL_HOST:
        return "is on an origin of the site's other than FRONTEND_URL: build it on FRONTEND_URL"
    if parts.path.startswith("//"):
        return "keeps FRONTEND_URL's trailing slash, and a doubled slash answers 308: strip it"
    if not address.startswith(BUILT_ON):
        return "is not built on FRONTEND_URL as it is set"
    if parts.path not in REGISTERED and _resolved(parts.path) in REGISTERED:
        return "resolves to a registered path but is spelled otherwise: spell it as registered"
    if parts.path not in REGISTERED:
        return "is not a whole registered path (frontend/tests/unit/publishedAssetUrls.json)"
    return None


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (tuple, list)):
        return [s for item in value for s in _strings(item)]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _strings(item)]
    return []


def _lines(code: CodeType) -> set[int]:
    """The lines a module's code runs, its functions' and comprehensions' included."""
    lines = {line for _, _, line in code.co_lines() if line}
    return lines.union(*(_lines(const) for const in code.co_consts if isinstance(const, CodeType)))


def _render(cases: dict) -> dict:
    """In the render's own interpreter: every string each function sends or returns, and each line of
    email_service.py that no render runs, the module's own loading included."""
    import asyncio
    import importlib

    ran: set[int] = set()

    def trace(frame, event, arg):
        if frame.f_code.co_filename != email_service.__file__:
            return None
        if event == "line":
            ran.add(frame.f_lineno)
        return trace

    sent: list[str] = []

    async def _record(to, subject, html, *args, **kwargs):
        sent.extend([subject, html])
        return {"id": "msg_test"}

    out: dict[str, list[str]] = {}
    sys.settrace(trace)
    try:
        importlib.reload(email_service)  # the module loads again, traced
        email_service.send_email = _record
        for name, inputs in cases.items():
            for kwargs in inputs:
                result = getattr(email_service, name)(**kwargs)
                if asyncio.iscoroutine(result):
                    result = asyncio.run(result)
                out.setdefault(name, []).extend(_strings(result) + sent)
                sent.clear()
    finally:
        sys.settrace(None)
    source = Path(email_service.__file__).read_text(encoding="utf-8")
    unrun = sorted(_lines(compile(source, email_service.__file__, "exec")) - ran)
    return {"mail": out, "unrun": [f"{line}: {source.splitlines()[line - 1].strip()}" for line in unrun]}


@pytest.fixture(scope="module")
def rendered() -> dict:
    env = {**os.environ, "FRONTEND_URL": SENTINEL, "CORS_ORIGINS_STR": ",".join(OTHER_ORIGINS), "PYTHONPATH": str(BACKEND)}
    run = subprocess.run(  # nosec B603: this file, run by this interpreter
        [sys.executable, __file__], input=json.dumps(RENDERS), env=env, cwd=BACKEND, capture_output=True, text=True, timeout=300
    )
    assert run.returncode == 0, f"the render failed:\n{run.stderr[-3000:]}"
    return json.loads(run.stdout.splitlines()[-1])


def _module_names(tree: ast.Module) -> set[str]:
    """The names a module binds outside any function or class: in its body, an if, a try, a with, a loop."""
    names: set[str] = set()
    bodies = [tree.body]
    while bodies:
        for node in bodies.pop():
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            names.update(t.id for t in targets if isinstance(t, ast.Name))
            bodies += [getattr(node, f) for f in ("body", "orelse", "finalbody") if isinstance(getattr(node, f, None), list)]
            bodies += [handler.body for handler in getattr(node, "handlers", [])]
    return names


def test_every_public_function_of_the_mail_module_is_rendered_here():
    names = _module_names(ast.parse(EMAIL_SERVICE.read_text(encoding="utf-8")))
    public = {name for name in names if not name.startswith("_") and callable(getattr(email_service, name, None))}
    assert public == set(RENDERS) | set(NOT_MAIL), (
        "render each public function of email_service here, with inputs that run each of its lines, or name it in "
        "NOT_MAIL with why it builds no mail"
    )
    assert all(RENDERS.values()) and not set(RENDERS) & set(NOT_MAIL)


def test_the_renders_run_every_line_of_the_mail_module(rendered):
    assert not rendered["unrun"], (
        "no render here runs these lines of email_service.py, so nothing reads the mail they build: add inputs to "
        "RENDERS that run them:\n" + "\n".join(rendered["unrun"])
    )


def _imported(node: ast.ImportFrom, path: Path) -> str:
    """The module an import names, a relative one resolved from the importing file's package."""
    if not node.level:
        return node.module or ""
    package = path.relative_to(BACKEND).with_suffix("").parts[: -node.level]
    return ".".join([*package, *([node.module] if node.module else [])])


def test_no_other_module_reaches_the_mail_modules_private_names():
    reached = []
    for path in sorted(APP.rglob("*.py")):
        if path == EMAIL_SERVICE:
            continue
        where, tree = path.relative_to(BACKEND), ast.parse(path.read_text(encoding="utf-8"))
        names = set()  # the names this module binds to email_service
        for node in ast.walk(tree):
            module = _imported(node, path) if isinstance(node, ast.ImportFrom) else None
            if module == "app.services.email_service":
                reached += [f"{where}:{node.lineno}: {a.name}" for a in node.names if a.name.startswith("_")]
            elif module == "app.services":
                names |= {a.asname or a.name for a in node.names if a.name == "email_service"}
            elif isinstance(node, ast.Import):
                names |= {a.asname for a in node.names if a.name == "app.services.email_service" and a.asname}
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr.startswith("_") and (
                (isinstance(node.value, ast.Name) and node.value.id in names)
                or (isinstance(node.value, ast.Attribute) and node.value.attr == "email_service")
            ):
                reached.append(f"{where}:{node.lineno}: email_service.{node.attr}")
    assert not reached, (
        "build mail through email_service's public functions, which this gate renders, not its private names:\n"
        + "\n".join(reached)
    )


def test_every_address_the_mail_carries_into_the_sites_files_is_registered_and_built_on_frontend_url(rendered):
    mail = rendered["mail"]
    assert set(mail) == set(RENDERS)
    problems = []
    for name, strings in mail.items():
        found = [address for sent in strings for address in read(sent)]
        assert TILE in found, f"{name}: the header's tile is not among the addresses read: the reader has narrowed"
        problems += [f"{name}: {address} {wrong}" for address in found if (wrong := problem(address))]
    assert not problems, (
        "the mail addresses a file of the site's other than by a whole registered path on FRONTEND_URL. Register a "
        "path mail shows in frontend/tests/unit/publishedAssetUrls.json in the same PR, and build its address on "
        "settings.FRONTEND_URL.rstrip('/') (LOGO_README.md > Published URLs stay put):\n" + "\n".join(sorted(set(problems)))
    )


def _img(src: str) -> str:
    return f'<td><img src="{src}" width="32" alt=""></td>'


# An unregistered path is spelled with a name no image will take.
BAD_2X = f"{BUILT_ON}assets/earningsnerd-unregistered@2x.png"
# Each way a sent string can carry an address into the site's files, and the look-alikes that must pass.
ADDRESSES = [
    # Flagged.
    ("an unregistered file", _img(BAD_2X), "not a whole registered path"),
    ("a srcset's second candidate", f'<img src="{TILE}" srcset="{TILE} 1x, {BAD_2X} 2x">', "not a whole registered path"),
    ("a srcset with no space after its comma", f'<img srcset="{TILE} 1x,{BAD_2X} 2x">', "not a whole registered path"),
    ("a srcset with a stray closing parenthesis", f'<img srcset="{TILE} 1x), {BAD_2X} 2x">', "not a whole registered path"),
    ("a srcset with nested parentheses", f'<img srcset="{TILE} ((1x), {BAD_2X} 2x">', "not a whole registered path"),
    ("a srcset with a no-break space", f'<img srcset="{TILE} {BAD_2X} 2x">', "not a whole registered path"),
    ("a srcset whose comma a client reads into the address", f'<img srcset="{TILE},x 1x">', "not a whole registered path"),
    ("an entity in the path", _img(f"{BUILT_ON}assets/earningsnerd-unregistered&#64;2x.png"), "not a whole registered path"),
    ("an entity a client reads into the path in text", f"<p>{TILE}&amp;v=2</p>", "not a whole registered path"),
    ("an entity in the text's address that a client reads as a registered path", f"<p>{BUILT_ON}assets/earningsnerd-appicon&#46;png</p>", None),
    ("a suffix a client reads into the path", _img(f"{TILE}(1)"), "not a whole registered path"),
    ("a CSS url() in a style attribute", f"<td style=\"background:url('{BUILT_ON}assets/x.png')\"></td>", "not a whole registered path"),
    ("a CSS url() in a style block", f"<style>.x{{background-image:url({BUILT_ON}assets/x.png)}}</style>", "not a whole registered path"),
    ("a relative CSS url() in a style block", "<style>.x{background-image:url(/assets/earningsnerd-unregistered.png)}</style>", "has no origin"),
    ("an image-set() in a style attribute", f"<td style=\"background-image:image-set('{BAD_2X}' 2x)\"></td>", "not a whole registered path"),
    ("a relative image-set() string in a style attribute", "<td style=\"background-image:image-set('/assets/earningsnerd-unregistered.png' 1x)\"></td>", "has no origin"),
    ("a CSS escape in a url()", f'<td style="background:url({BUILT_ON}\\61ssets/x.png)"></td>', "not a whole registered path"),
    ("an image inside Outlook's conditional comment", f'<!--[if mso]><v:image src="{BUILT_ON}assets/x.png" /><![endif]-->', "not a whole registered path"),
    ("a VML fill inside Outlook's conditional comment", f'<!--[if gte mso 9]><v:fill type="tile" src="{BUILT_ON}icons/x.png" /><![endif]-->', "not a whole registered path"),
    ("a link to a file", f'<a href="{BUILT_ON}icons/icon-192.png">icon</a>', "not a whole registered path"),
    ("a root file", f'<link rel="icon" href="{BUILT_ON}favicon.ico">', "not a whole registered path"),
    ("a meta tag's logo", f'<meta itemprop="logo" content="{BUILT_ON}assets/x.png">', "not a whole registered path"),
    ("an address in the plain-text copy", f'<pre style="display:none">See {BUILT_ON}assets/x.png.</pre>', "not a whole registered path"),
    ("an address in angle brackets in a plain-text copy", f"Our tile: <{BAD_2X}>", "not a whole registered path"),
    ("an address in text split by a comment", f"<p>{BUILT_ON}as<!-- -->sets/x.png</p>", "not a whole registered path"),
    ("an address in text split by a wbr", f"<p>{BUILT_ON}as<wbr>sets/x.png</p>", "not a whole registered path"),
    ("a relative address under a base", f'<base href="{TILE}"><img src="earningsnerd-unregistered.png">', "not a whole registered path"),
    ("a parent segment under a base", f'<base href="{BUILT_ON}x/"><img src="../assets/earningsnerd-unregistered.png">', "not a whole registered path"),
    ("backslashes in an address", _img(f"https://{SENTINEL_HOST}\\assets\\x.png"), "not a whole registered path"),
    ("a dot segment", _img(f"{BUILT_ON}./assets/earningsnerd-appicon.png"), "spelled otherwise"),
    ("a parent segment", _img(f"{BUILT_ON}icons/../assets/earningsnerd-appicon.png"), "spelled otherwise"),
    ("a parent segment after a directory the site does not serve", _img(f"{BUILT_ON}x/../assets/earningsnerd-appicon.png"), "spelled otherwise"),
    ("a percent-escape", _img(f"{BUILT_ON}%61ssets/earningsnerd-appicon.png"), "spelled otherwise"),
    ("a relative path", _img("/assets/earningsnerd-appicon.png"), "has no origin"),
    ("a relative path with a parent segment and no base", _img("x/../assets/earningsnerd-unregistered.png"), "has no origin"),
    ("www hard-coded", _img("https://www.earningsnerd.io/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("the apex, protocol-relative", _img("//earningsnerd.io/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("the API host", _img("https://api.earningsnerd.io/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("a host in capitals", _img("https://WWW.EarningsNerd.io/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("another origin the site sets", _img(f"{OTHER_ORIGINS[0]}/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("a loopback host", _img("http://localhost:3000/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("a bare www address in text", "<p>See www.earningsnerd.io/assets/earningsnerd-appicon.png</p>", "an origin of the site's other than FRONTEND_URL"),
    ("FRONTEND_URL unstripped", _img(f"{SENTINEL}/assets/earningsnerd-appicon.png"), "keeps FRONTEND_URL's trailing slash"),
    ("FRONTEND_URL on another scheme", _img(f"http://{SENTINEL_HOST}/assets/earningsnerd-appicon.png"), "not built on FRONTEND_URL"),
    ("a host's trailing dot", _img(f"https://{SENTINEL_HOST}./assets/earningsnerd-appicon.png"), "not built on FRONTEND_URL"),
    # Pass.
    ("the tile on FRONTEND_URL", _img(TILE), None),
    ("a registered path with a query and a fragment", _img(f"{TILE}?v=2#top"), None),
    ("a page of the site's", f'<a href="{BUILT_ON}dashboard/settings">Settings</a>', None),
    ("another site's file", _img("https://cdn.example.com/assets/x.png"), None),
    ("a mail link", '<a href="mailto:support@earningsnerd.io">Write to us</a>', None),
    ("a sentence's full stop after the tile, in text", f"<p>The tile is {TILE}.</p>", None),
    ("the tile in angle brackets in a plain-text copy", f"Our tile: <{TILE}>", None),
    ("a srcset of two registered candidates", f'<img srcset="{TILE} 1x, {TILE}?v=2 2x">', None),
]
# One page for each attribute that holds an address, written out so narrowing the reader fails a case.
ADDRESSES += [
    (f"an address in {name}", f'<x {name}="{BUILT_ON}assets/earningsnerd-unregistered.png">', "not a whole registered path")
    for name in ("src", "href", "background", "poster", "action", "formaction", "cite", "longdesc", "data", "xlink:href", "o:href")
]
# A planted string that opens with markup is read as a page, as _wrap_html builds one; the rest are plain text.
ADDRESSES = [(what, f"<!doctype html>{sent}" if sent.startswith("<") else sent, expected) for what, sent, expected in ADDRESSES]


@pytest.mark.parametrize("sent, expected", [form[1:] for form in ADDRESSES], ids=[form[0] for form in ADDRESSES])
def test_the_reader_scores_every_planted_address(sent, expected):
    found = read(sent)
    assert found, "the reader found no address"
    verdicts = [wrong for address in found if (wrong := problem(address))]
    if expected is None:
        assert not verdicts, verdicts
    else:
        assert any(expected in wrong for wrong in verdicts), f"expected {expected!r}, got {verdicts} from {found}"


if __name__ == "__main__":  # the render, in an interpreter of its own (the mail fixture)
    print(json.dumps(_render(json.loads(sys.stdin.read()))))
