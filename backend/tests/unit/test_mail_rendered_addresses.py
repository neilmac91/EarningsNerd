"""Gate: every address the mail carries into the site's files is a registered path on FRONTEND_URL.

``test_mail_published_assets.py`` reads the code that builds mail, and cannot follow a value through it.
This gate reads the mail as it is sent, so an address is checked however the code derived it: a
``.replace``, an alias, a join, a fill, a helper, a rebinding (``frontend/public/assets/LOGO_README.md``
› Published URLs stay put).

It calls every public function of ``email_service``, the module that builds the mail, with inputs that
pass each of its parameters at least once and run every line of the module, save a line no input can
reach, named in ``UNRUN`` with why. Checks hold the inputs to both, so a branch they skip fails here
until they take it. It reads every public value the module holds too, which a caller may send. It runs
them in an interpreter of their own, with these settings, which a check holds the render to:
- ``FRONTEND_URL`` is set to a sentinel that keeps its trailing slash, so an address built when the
  module loads is built on the sentinel too;
- the site's other origins (``CORS_ORIGINS_STR``) are set to hosts of their own.

It reads every string a function sends or returns. A page, as ``_wrap_html`` builds it, is read as its
markup; any other string (a plain-text copy, a subject) as markup and as the text it is, as
``_hidden_text`` sends it. In them it reads:
- each attribute that holds an address: ``srcset`` candidate by candidate, as HTML parses it; a
  ``<meta>`` tag's content; a relative address, resolved against a ``<base href>``;
- each URL in CSS, in a ``style`` attribute or a ``<style>`` block, with its escapes decoded: a ``url()``,
  a quoted string, such as an ``image-set()``'s, and an absolute URL, such as an unclosed ``url()``'s;
- the markup inside Outlook's conditional comments;
- every absolute URL in the text, ``www.`` included, read across a comment or a ``<wbr>``.

An address into the site's files is one into a directory or a root file under ``frontend/public``, on
an origin of the site's or on none. It is resolved as a client resolves it: backslashes, dot segments,
percent-escapes, a host's trailing dot. Each such address must be a whole registered path
(``frontend/tests/unit/publishedAssetUrls.json``), spelled as registered, its query and fragment aside.
It must also be built on ``FRONTEND_URL`` with that slash stripped:
- on no other origin of the site's: ``earningsnerd.io`` or a host under it, another origin the settings
  set, or a loopback host, a setting's local default;
- never without an origin, since a mail has no base URL, nor relative to a ``<base href>``, which a mail
  client may drop;
- never after a doubled slash, which answers 308.

The render list is held to ``email_service``'s public functions, save those that build no mail, each
named with why (``NOT_MAIL``), and no other module in ``backend/app`` may reach its private names, so a
new mail fails here until it is rendered. Planted modules score that check. What it cannot see:
- an address in a form it does not read: an attribute outside the list it reads, a script;
- which way a branch within one line goes (``x if c else y``, ``a or b``, a lookup), so a value no input
  passes may pick an address no render reads;
- a line named in ``UNRUN``;
- the links a caller hands in, for which the inputs are stand-ins; the code scan reads the callers;
- what runs before the mail is built, elsewhere, such as a job rebinding a module's name;
- an origin of the site's that a setting the render leaves alone points at another site's host;
- a private name reached through ``getattr`` or ``importlib``;
- mail built or finished outside ``email_service``: ``routers/contact.py``'s confirmation (E56), the
  internal admin and team notices, and what a caller adds to a page before it sends it
  (``data_quality_service.run_and_email`` appends the report's text copy, as ``_hidden_text`` would).

It also holds every page it renders to two of the shell's rules, which ``test_mail_header_template.py``
states and plants and ``tests/support/mail_styles.py`` reads as a client does:
- the header keeps its set size where a phone view enlarges text, and every other line, a mail's own
  included, is left to the view;
- a run with nowhere to break, such as a link with its token, can break anywhere once it is long enough
  to fill the panel, so a view that enlarges it cannot widen the panel past the header. The inputs print
  such runs at their real lengths, a link with a 43-character token and a report's hashes and addresses,
  and a check holds the renders that print one to ``PRINTS_LONG_RUNS``.
"""
import ast
import html
import inspect
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
from tests.support.mail_styles import long_run_problems, long_runs, text_size_problems

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
# A link as a caller builds one: a token as secrets.token_urlsafe(32) draws it, 43 characters, here with no
# hyphen to break at.
LINK = "https://e.test/reset-password?token=Qm9va3NhbmRjb2ZmZWVhbmRyZWFkaW5nYWxsZGF5MDE"
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
DIGEST = dict(name="Ada", items=[
    dict(DIGEST_ITEM, filing_id=1, wording_changes={"has_changes": True, "items_total": 2}),
    dict(DIGEST_ITEM, filing_url=LINK),
    DIGEST_ITEM,
])
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
    "weekly_readout": {
        "status": "complete", "reason": None, "dimensions": {"accuracy": 4.5},
        "source_sha": "3f9c2a7d1e0b8c4f6a5d2e1b0c9f8a7e6d5c4b3a",
        "cohort_sha256": "9b1c3e5a7d9f2b4d6f8a0c2e4a6c8e0b2d4f6a8c0e2a4c6e8a0b2c4d6e8f0a1b",
        "run_url": "https://github.com/neilmac91/EarningsNerd/actions/runs/38707048863",
        "artifact_url": "https://github.com/neilmac91/EarningsNerd/actions/runs/38707048863/artifacts/4123456789",
    },
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
# The lines of email_service.py no render here can run, by their text, each with why: a handler for a
# failure the stand-in send never raises, a branch on a setting the render cannot take, an import only a
# type checker runs.
UNRUN: dict[str, str] = {}

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
    """The addresses in CSS, its escapes decoded: each url(); each quoted string, which is how image-set()
    and @import spell one; and every absolute URL, such as an unclosed url()'s, which a client still reads."""
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


class _Relative(str):
    """An address written relative to the page's <base href>, resolved against it."""


def addresses(page: str) -> list[str]:
    """Every address in a page, a relative one resolved against the page's <base href>."""
    parser = _Addresses()
    parser.feed(page)
    parser.close()
    relative = [parser.base and not urlsplit(a).scheme and not a.startswith("//") for a in parser.found]
    return [_Relative(urljoin(parser.base, a)) if r else a for a, r in zip(parser.found, relative)]


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
    relative = isinstance(address, _Relative)
    address = re.sub(r"[\t\n\r]", "", address.strip(_ASCII_SPACE)).replace("\\", "/")  # as a URL parser reads it
    address = re.sub(r"^(https?:)/*", r"\1//", address, flags=re.IGNORECASE)  # https:/x and https:x are https://x
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
    if relative:
        return "is relative to the page's <base href>, which a mail client may drop: build it on FRONTEND_URL"
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


def _public_values(module, source: str) -> dict[str, list[str]]:
    """The strings of each public value a module binds that is not a function, which a caller may send."""
    return {
        name: _strings(getattr(module, name))
        for name in sorted(_module_names(ast.parse(source)))
        if not name.startswith("_") and hasattr(module, name) and not callable(getattr(module, name))
    }


def _unpassed(function, inputs: list[dict]) -> set[str]:
    """The parameters of ``function`` that no input passes."""
    parameters = inspect.signature(function).parameters.values()
    return {p.name for p in parameters if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)} - set().union(*inputs)


def _unrun_left(unrun: list[str], allowed: dict[str, str]) -> tuple[list[str], list[str]]:
    """The lines ``allowed`` names that run now, or are gone, and the unrun lines it does not name."""
    texts = {line.split(": ", 1)[1]: line for line in unrun}
    return sorted(set(allowed) - set(texts)), [line for text, line in texts.items() if text not in allowed]


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
        sent.extend(_strings([to, subject, html, list(args), kwargs]))
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
    values = _public_values(email_service, source)
    lines = _lines(compile(source, email_service.__file__, "exec"))
    unrun = sorted(lines - ran)
    return {
        "mail": out,
        "values": values,
        "lines": len(lines),
        "unrun": [f"{line}: {source.splitlines()[line - 1].strip()}" for line in unrun],
        "settings": {"FRONTEND_URL": email_service.settings.FRONTEND_URL, "CORS_ORIGINS": email_service.settings.CORS_ORIGINS},
    }


@pytest.fixture(scope="module")
def rendered() -> dict:
    env = {**os.environ, "FRONTEND_URL": SENTINEL, "CORS_ORIGINS_STR": ",".join(OTHER_ORIGINS), "PYTHONPATH": str(BACKEND)}
    run = subprocess.run(  # nosec B603: this file, run by this interpreter
        [sys.executable, __file__], env=env, cwd=BACKEND, capture_output=True, text=True, timeout=300
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


def test_the_render_runs_on_the_sentinel_and_on_origins_of_its_own(rendered):
    # The slash is what shows a FRONTEND_URL left unstripped, through an alias or a fill the code scan
    # cannot follow; the hosts are what show an address on another origin of the site's.
    assert SENTINEL.endswith("/") and rendered["settings"] == {"FRONTEND_URL": SENTINEL, "CORS_ORIGINS": list(OTHER_ORIGINS)}, (
        f"the render ran on {rendered['settings']}: run it on FRONTEND_URL={SENTINEL} and CORS_ORIGINS_STR={','.join(OTHER_ORIGINS)}"
    )


def test_every_public_function_of_the_mail_module_is_rendered_here():
    names = _module_names(ast.parse(EMAIL_SERVICE.read_text(encoding="utf-8")))
    public = {name for name in names if not name.startswith("_") and callable(getattr(email_service, name, None))}
    assert public == set(RENDERS) | set(NOT_MAIL), (
        "render each public function of email_service here, with inputs that run each of its lines, or name it in "
        "NOT_MAIL with why it builds no mail"
    )
    assert all(RENDERS.values()) and not set(RENDERS) & set(NOT_MAIL)
    for name, inputs in RENDERS.items():
        missing = _unpassed(getattr(email_service, name), inputs)
        assert not missing, f"{name}: no input passes {sorted(missing)}, and a value no input passes may pick an address no render reads"


def test_the_renders_run_every_line_of_the_mail_module(rendered):
    assert rendered["lines"] > 300, f"the coverage check counts only {rendered['lines']} lines of email_service.py: it has narrowed"
    stale, left = _unrun_left(rendered["unrun"], UNRUN)
    assert not stale, f"these lines named in UNRUN run now, or are gone: take them out of it: {stale}"
    assert not left, (
        "no render here runs these lines of email_service.py, so nothing reads the mail they build. Add inputs to "
        "RENDERS that run them, or, for a line no input can reach, name it in UNRUN with why:\n" + "\n".join(left)
    )


def _imported(node: ast.ImportFrom, path: Path, app: Path) -> str:
    """The module an import names, a relative one resolved from the importing file's package."""
    if not node.level:
        return node.module or ""
    package = path.relative_to(app.parent).with_suffix("").parts[: -node.level]
    return ".".join([*package, *([node.module] if node.module else [])])


def _private(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _private_reaches(app: Path) -> tuple[list[str], list[str]]:
    """Where a module under ``app`` reaches the mail module's private names, and the modules that import
    the mail module or a name from it."""
    reached: list[str] = []
    importers: list[str] = []
    for path in sorted(app.rglob("*.py")):
        if path == app / "services" / "email_service.py":
            continue
        where, tree = str(path.relative_to(app.parent)), ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()  # the names this module binds to email_service
        imports = False
        for node in ast.walk(tree):
            module = _imported(node, path, app) if isinstance(node, ast.ImportFrom) else None
            if module == "app.services.email_service":
                imports = True
                reached += [f"{where}:{node.lineno}: {a.name}" for a in node.names if _private(a.name)]
            elif module == "app.services" and any(a.name == "email_service" for a in node.names):
                imports = True
                names |= {a.asname or a.name for a in node.names if a.name == "email_service"}
            elif isinstance(node, ast.Import) and any(a.name == "app.services.email_service" for a in node.names):
                imports = True
                names |= {a.asname for a in node.names if a.name == "app.services.email_service" and a.asname}
        while True:  # a name bound to one of those names holds the module too
            rebound = {
                target.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in names
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if rebound <= names:
                break
            names |= rebound
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and _private(node.attr) and (
                (isinstance(node.value, ast.Name) and node.value.id in names)
                or (isinstance(node.value, ast.Attribute) and node.value.attr == "email_service")
            ):
                reached.append(f"{where}:{node.lineno}: email_service.{node.attr}")
        if imports:
            importers.append(where)
    return reached, importers


def test_no_other_module_reaches_the_mail_modules_private_names():
    reached, importers = _private_reaches(APP)
    assert {"app/services/data_quality_service.py", "app/routers/auth.py"} <= set(importers) and len(importers) >= 6, (
        f"the walk no longer finds the modules that import email_service: {importers}"
    )
    assert not reached, (
        "build mail through email_service's public functions, which this gate renders, not its private names:\n"
        + "\n".join(reached)
    )


# Each way another module can reach the mail module's private names, and the look-alikes that must pass.
REACHES = [
    ("a private name imported by name", "from app.services.email_service import _wrap_html\n", True),
    ("a private name imported under another name", "from app.services.email_service import _wrap_html as shell\n", True),
    ("a private name through the module imported from its package", "from app.services import email_service\nemail_service._wrap_html('x')\n", True),
    ("a private name through the module imported under another name", "from app.services import email_service as mail\nmail._hidden_text('x')\n", True),
    ("a private name through the module's dotted path", "import app.services.email_service\napp.services.email_service._wrap_html('x')\n", True),
    ("a private name through the module imported as a name", "import app.services.email_service as mail\nmail._wrap_html('x')\n", True),
    ("a private name through a relative import of the name", "from .email_service import _wrap_html\n", True),
    ("a private name through a relative import of the module", "from . import email_service as mail\nmail._wrap_html('x')\n", True),
    ("a private name through a name bound to the module", "from app.services import email_service\nes = email_service\nes._wrap_html('x')\n", True),
    ("a private name imported inside a function", "def f():\n    from app.services.email_service import _wrap_html\n    return _wrap_html('x')\n", True),
    ("a public function imported by name", "from app.services.email_service import send_daily_digest\n", False),
    ("a public function through the module", "from app.services import email_service\nemail_service.send_daily_digest()\n", False),
    ("a dunder of the module", "from app.services import email_service\nNAME = email_service.__name__\n", False),
    ("another module's private name", "from app.services import resend_service\nresend_service._client()\n", False),
]


@pytest.mark.parametrize("source, reaches", [case[1:] for case in REACHES], ids=[case[0] for case in REACHES])
def test_the_private_reach_check_scores_every_planted_module(tmp_path, source, reaches):
    services = tmp_path / "app" / "services"
    services.mkdir(parents=True)
    (services / "email_service.py").write_text("def _wrap_html(body):\n    return body\n", encoding="utf-8")
    (services / "recap_mail.py").write_text(source, encoding="utf-8")
    reached, importers = _private_reaches(tmp_path / "app")
    assert bool(reached) == reaches, reached
    assert importers == (["app/services/recap_mail.py"] if "email_service" in source else [])


def test_the_completeness_check_reads_every_name_the_module_binds():
    source = (
        "def a(): ...\nasync def b(): ...\nclass C:\n    inner = 1\nd = 1\ne: int = 2\n"
        "if True:\n    def f(): ...\nelse:\n    g = 1\n"
        "try:\n    def h(): ...\nexcept Exception:\n    i = 1\nelse:\n    j = 1\nfinally:\n    k = 1\n"
        "for _ in ():\n    m = 1\nwhile False:\n    n = 1\nwith open('x') as handle:\n    o = 1\n"
        "def p():\n    local = 1\n"
    )
    assert _module_names(ast.parse(source)) == {*"abCdefghijkmnop"}, _module_names(ast.parse(source))


def test_the_checks_on_the_inputs_score_their_planted_cases():
    import types

    module = types.ModuleType("planted")
    source = "PAGE = '<p>x</p>'\nPAIR = ('a', 'b')\n_HIDDEN = 'x'\n\n\ndef send(to, subject, html=''):\n    return None\n"
    exec(compile(source, "planted", "exec"), module.__dict__)  # nosec B102: the planted source above
    assert _public_values(module, source) == {"PAGE": ["<p>x</p>"], "PAIR": ["a", "b"]}
    assert _unpassed(module.send, [dict(to="t", subject="s")]) == {"html"}
    assert _unpassed(module.send, [dict(to="t", subject="s"), dict(to="t", subject="s", html="h")]) == set()
    unrun = ["8: from app.models import User", "12: raise"]
    assert _unrun_left(unrun, {}) == ([], unrun)
    assert _unrun_left(unrun, {"raise": "the stand-in send never raises", "gone()": "a line no longer there"}) == (["gone()"], unrun[:1])


def test_the_coverage_check_counts_the_lines_inside_functions_and_comprehensions():
    source = "X = 1\n\n\ndef f():\n    y = 2\n\n    def g():\n        return (w for w in ())\n\n    return [z for z in g()]\n"
    lines = _lines(compile(source, "planted", "exec"))
    assert {1, 4, 5, 7, 8, 10} <= lines and not {2, 3, 6, 9} & lines, lines


def test_every_address_the_mail_carries_into_the_sites_files_is_registered_and_built_on_frontend_url(rendered):
    mail = rendered["mail"]
    assert set(mail) == set(RENDERS)
    problems = []
    for name, strings in mail.items():
        found = [address for sent in strings for address in read(sent)]
        assert TILE in found, f"{name}: the header's tile is not among the addresses read: the reader has narrowed"
        problems += [f"{name}: {address} {wrong}" for address in found if (wrong := problem(address))]
    for name, strings in rendered["values"].items():  # a value the module holds, which a caller may send
        problems += [f"{name}: {address} {wrong}" for sent in strings for address in read(sent) if (wrong := problem(address))]
    assert not problems, (
        "the mail addresses a file of the site's other than by a whole registered path on FRONTEND_URL. Register a "
        "path mail shows in frontend/tests/unit/publishedAssetUrls.json in the same PR, and build its address on "
        "settings.FRONTEND_URL.rstrip('/') (LOGO_README.md > Published URLs stay put):\n" + "\n".join(sorted(set(problems)))
    )


def _pages(rendered: dict) -> list[tuple[str, str]]:
    pages = [(name, sent) for name, strings in rendered["mail"].items() for sent in strings if _PAGE.match(sent)]
    assert len({name for name, _ in pages}) == len(RENDERS), "a render sent no page"
    return pages


def test_every_page_sent_keeps_the_headers_set_size_and_leaves_the_rest_to_the_view(rendered):
    problems = [f"{name}: {problem}" for name, page in _pages(rendered) for problem in text_size_problems(page)]
    assert not problems, "\n".join(sorted(set(problems)))


# The renders whose pages print a run long enough for the long-run rule to read: a link with its token, a
# report's hash or address. Held as it is, so inputs that shorten a run fail here too.
PRINTS_LONG_RUNS = frozenset({
    "render_welcome_email", "send_waitlist_welcome_email", "render_referral_success_email", "send_referral_success_email",
    "send_verification_email", "send_invite_email", "send_password_reset_email", "render_data_quality_report",
})


def test_every_long_run_a_page_sent_shows_can_break(rendered):
    pages = _pages(rendered)
    printed = {name for name, page in pages if long_runs(page)}
    assert printed == PRINTS_LONG_RUNS, (
        f"the renders that print a long run are {sorted(printed)}: hold PRINTS_LONG_RUNS to them, with inputs that print "
        "each such line at its real length"
    )
    problems = [f"{name}: {problem}" for name, page in pages for problem in long_run_problems(page)]
    assert not problems, "\n".join(sorted(set(problems)))


def _img(src: str) -> str:
    return f'<td><img src="{src}" width="32" alt=""></td>'


# An unregistered path is spelled with a name no image will take, save two files the site serves that the
# register leaves out (icons/icon-192.png, favicon.ico).
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
    ("a suffix a client reads into the path", _img(f"{TILE}(1)"), "not a whole registered path"),
    ("a CSS url() in a style attribute", f"<td style=\"background:url('{BUILT_ON}assets/x.png')\"></td>", "not a whole registered path"),
    ("a CSS url() in a style block", f"<style>.x{{background-image:url({BUILT_ON}assets/x.png)}}</style>", "not a whole registered path"),
    ("a relative CSS url() in a style block", "<style>.x{background-image:url(/assets/earningsnerd-unregistered.png)}</style>", "has no origin"),
    ("an image-set() in a style attribute", f"<td style=\"background-image:image-set('{BAD_2X}' 2x)\"></td>", "not a whole registered path"),
    ("a relative image-set() string in a style attribute", "<td style=\"background-image:image-set('/assets/earningsnerd-unregistered.png' 1x)\"></td>", "has no origin"),
    ("an unclosed url() in a style attribute", f'<td style="background:url({BUILT_ON}assets/x.png"></td>', "not a whole registered path"),
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
    ("a relative address under a base", f'<base href="{TILE}"><img src="earningsnerd-unregistered.png">', "relative to the page's <base href>"),
    ("a parent segment under a base", f'<base href="{BUILT_ON}x/"><img src="../assets/earningsnerd-unregistered.png">', "relative to the page's <base href>"),
    ("a registered path relative to a base on FRONTEND_URL", f'<base href="{BUILT_ON}"><img src="assets/earningsnerd-appicon.png">', "relative to the page's <base href>"),
    ("a root-relative registered path under a base", f'<base href="{BUILT_ON}"><img src="/assets/earningsnerd-appicon.png">', "relative to the page's <base href>"),
    ("a special scheme's slashes missing", _img("https:/frontend.example.test/assets/earningsnerd-unregistered.png"), "not a whole registered path"),
    ("a special scheme with no slashes", _img("https:frontend.example.test/assets/earningsnerd-unregistered.png"), "not a whole registered path"),
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
    ("a loopback address", _img("http://127.0.0.1:3000/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("the IPv6 loopback", _img("http://[::1]:3000/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("a host under localhost", _img("http://app.localhost:3000/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
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
    ("an entity in the text's address that a client reads as a registered path", f"<p>{BUILT_ON}assets/earningsnerd-appicon&#46;png</p>", None),
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
    print(json.dumps(_render(RENDERS)))
