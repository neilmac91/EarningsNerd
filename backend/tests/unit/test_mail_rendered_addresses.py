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

It reads every string a function sends, through the module's name for the transport or the transport itself, or
returns. A page, as ``_wrap_html`` builds it, is read as its markup; any other string (a plain-text copy, a
subject) as markup and as the text it is, as ``_hidden_text`` sends it. In them it reads:
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
new mail fails here until it is rendered; every mail the module sends must be a page the shell built, each
``send_`` function sending one and no render or build function any (planted as stub modules the same render runs).
Nor may a module build an HTML page outside the shell, ``_wrap_html`` (a string that opens a doctype,
``<html>``, ``<head>`` or ``<body>``), save those ``OWN_PAGES`` lists, or send mail, through the
transport (``resend_service``), the delivery queue, which sends the pages it is handed, or the provider
itself, save those ``SENDERS`` lists with how many times each names a send and what it sends, so a new
sender, or a listed one that names a send once more, fails here until it builds its mail through
``email_service`` or is listed. Planted modules score each check. What it cannot see:
- an address in a form it does not read: an attribute outside the list it reads, a script;
- which way a branch within one line goes (``x if c else y``, ``a or b``, a lookup), so a value no input
  passes may pick an address no render reads;
- a line named in ``UNRUN``;
- the links a caller hands in, for which the inputs are stand-ins; the code scan reads the callers;
- what runs before the mail is built, elsewhere, such as a job rebinding a module's name;
- an origin of the site's that a setting the render leaves alone points at another site's host;
- a private name, the transport or the queue reached through ``getattr`` or ``importlib``; a private name
  read through another name for the mail module than an import of it binds (a re-exporting module's,
  ``mailer.es``, or a package's attribute bound to a name, ``es = services.email_service``); the transport
  or the queue bound by unpacking (``q, t = a, b``) or held as a class's attribute; a send
  behind a helper or a wrapper module, counted once however often its callers call it; and a call of the
  mail provider that names neither its settings nor its address;
- mail built or finished outside ``email_service``, in the modules ``SENDERS`` lists:
  ``routers/contact.py``'s confirmation (E56), the internal admin and team notices, and what a caller adds
  to a page before it sends it (``data_quality_service.run_and_email`` appends the report's text copy, as
  ``_hidden_text`` would).

It also holds every page it renders to the shell's page rules, which ``test_mail_header_template.py``
states and plants, and which ``tests/support/mail_styles.py`` models as Blink and WebKit read a page's
inline styles:
- the header keeps its set size in a view that enlarges small text, and every other line, a mail's own
  included, is left to the view;
- a run with nowhere to break, such as a link with its token, can break anywhere once it is long enough
  to fill the panel's text column on the narrowest phone, so it cannot hold the page wider than the
  screen. The inputs print such runs at their real lengths, and a check holds them to it: every input
  that names the reader passes a name typed as an address, 34 characters, and every render that takes a
  name is given that one; every recipient is an address of 39; every company is a real EDGAR name whose
  longest run is 19 characters; every link a caller hands in carries a 43-character token, each value held
  to that length; and an input prints each time slot an earnings-day row can show. The report's hashes and
  addresses are its own. ``PRINTS_LONG_RUNS`` holds how many long runs each render's pages print, page by
  page;
- that rule reaches no table, whose amounts it would split;
- no box a client other than classic Outlook shows is set wider than the room its parent gives it on the
  narrowest phone, and classic Outlook, which reads no ``max-width``, holds each column capped at 600 px
  at 600 px;
- the page sets the shell's viewport alone, at the phone's own width;
- every colour a page writes, in a style or an attribute HTML maps to a colour, is a design token's
  (``DESIGN.md``'s frontmatter), as six-digit hex, in its own view and in classic Outlook's, and every
  link sets a colour of its own that a browser takes, which a client would otherwise paint its link blue.

And it holds every page to open ``<body>`` with the mail's preheader, the line an inbox lists beside the
subject (``preheader_problems``, planted in ``PREHEADERS``): one, hidden from the view and from classic
Outlook's, plain text of ``PREHEADER_LIMIT`` characters at most with no link or address, since an inbox shows
it before the mail is opened, and the fill after it, so in most previews the header's words do not follow it.
A list keeps to the limit however long it runs (``_listed``, pinned with fifty filings and four slots). What it
cannot see: whether a line says what its mail says, which review reads; a bare host with no path, which passes
because a company's name can be shaped like one; and a line longer than the limit for a company whose name is
longer than the inputs' (the alert's line, and the earnings alert's for one company, print the name as the
caller hands it in, first, so a preview that cuts the line cuts what follows it).
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
import tinycss2

from app.services import email_service
from tests.support.mail_styles import (
    colour_problems,
    fixed_width_problems,
    long_run_problems,
    long_runs,
    outlook_width_problems,
    reach_problems,
    text_size_problems,
    viewports,
)

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

# A recipient as a reader may sign up: an address, 39 characters with nowhere to break.
TO = "firstname.lastname@recipientcompany.com"
# A name as a reader may type one: an address, 34 characters with nowhere to break.
NAME = "firstname.lastname@companyname.com"
# A company as EDGAR names one, a real registrant: its longest run, "BIOPHARMACEUTICALS,", is 19 characters in
# capitals, the alert's bold among them.
COMPANY = "PROVECTUS BIOPHARMACEUTICALS, INC."
# A link as a caller builds one: a token as secrets.token_urlsafe(32) draws it, 43 characters, here with no
# hyphen to break at.
LINK = "https://e.test/reset-password?token=Qm9va3NhbmRjb2ZmZWVhbmRyZWFkaW5nYWxsZGF5MDE"  # gitleaks:allow
WAITLIST = dict(name=NAME, position=3, referral_link=LINK, verification_link=LINK)
REFERRAL = dict(name=NAME, new_position=2, referral_link=LINK)
FILING = dict(name=NAME, company_name=COMPANY, ticker="PVCT", filing_type="10-K", filing_date="2026-01-01")
ALERTS = [
    dict(FILING, filing_id=1, wording_changes={"has_changes": True, "items_total": 3}),
    dict(FILING, filing_id=1, wording_changes={"has_changes": False, "items_total": 0}),
    dict(FILING, filing_id=1, wording_changes={"prior_reference_only": True, "items_total": 2}),
    dict(FILING, filing_url=LINK),
    FILING,
]
DIGEST_ITEM = {"company_name": COMPANY, "ticker": "PVCT", "filing_type": "10-K", "filing_date": "2026-01-01"}
DIGEST = dict(name=NAME, items=[
    dict(DIGEST_ITEM, filing_id=1, wording_changes={"has_changes": True, "items_total": 2}),
    dict(DIGEST_ITEM, filing_url=LINK),
    DIGEST_ITEM,
])
# The second is an estimated event, a provider's date, in the shape send_earnings_day_alerts builds.
EARNINGS = [
    dict(name=NAME, items=[{"ticker": "PVCT", "company_name": COMPANY, "time": "bmo"}, {"ticker": "BETA", "time": "dmh", "status": "reported"}]),
    dict(name=NAME, items=[{"ticker": "PVCT", "company_name": COMPANY, "time": "amc", "status": "estimated"}]),
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
    "send_verification_email": [dict(to_email=TO, name=NAME, verification_link=LINK)],
    "send_invite_email": [dict(to_email=TO, magic_link=LINK), dict(to_email=TO, magic_link=LINK, name=NAME)],
    "send_password_reset_email": [dict(to_email=TO, name=NAME, reset_link=LINK)],
    "send_oauth_linked_email": [dict(to_email=TO, name=NAME, provider="Google")],
    "send_account_exists_email": [dict(to_email=TO, name=NAME, login_link=LINK, reset_link=LINK)],
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


def _render(cases: dict, module=email_service) -> dict:
    """In the render's own interpreter: every string each function of the mail module sends or returns, the HTML
    of each mail it sends, through its own name for the transport or the transport itself, and each line of the
    module that no render runs, its own loading included."""
    import asyncio
    import importlib

    from app.services import resend_service

    ran: set[int] = set()

    def trace(frame, event, arg):
        if frame.f_code.co_filename != module.__file__:
            return None
        if event == "line":
            ran.add(frame.f_lineno)
        return trace

    sent: list[str] = []
    sent_html: list[str] = []

    async def _record(to, subject, html, *args, **kwargs):
        sent.extend(_strings([to, subject, html, list(args), kwargs]))
        sent_html.append(html)
        return {"id": "msg_test"}

    out: dict[str, list[str]] = {}
    html_sent: dict[str, list[str]] = {}
    transport = resend_service.send_email
    sys.settrace(trace)
    try:
        resend_service.send_email = _record  # a send through the transport is recorded, however the module reaches it
        importlib.reload(module)  # the module loads again, traced, and binds the transport as recorded
        for name, inputs in cases.items():
            for kwargs in inputs:
                result = getattr(module, name)(**kwargs)
                if asyncio.iscoroutine(result):
                    result = asyncio.run(result)
                out.setdefault(name, []).extend(_strings(result) + sent)
                html_sent.setdefault(name, []).extend(sent_html)
                sent.clear()
                sent_html.clear()
    finally:
        sys.settrace(None)
        resend_service.send_email = transport
    source = Path(module.__file__).read_text(encoding="utf-8")
    values = _public_values(module, source)
    lines = _lines(compile(source, module.__file__, "exec"))
    unrun = sorted(lines - ran)
    return {
        "mail": out,
        "html_sent": html_sent,
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


# The HTML pages a module of backend/app builds outside the shell, with how many: contact.py's notice to the team
# and its confirmation to the person who wrote in, until E56 moves the confirmation into the shell, and a PDF
# export's page, which is no mail. Equalities (lessons/test-allowlist-caps-are-equalities.md): a page that moves into
# the shell lowers its count in the same diff.
OWN_PAGES = {"app/routers/contact.py": 2, "app/services/pdf_branding.py": 1}
_OPENS_A_PAGE = re.compile(r"<(?:html|head|body)[\s>]|<!doctype\s", re.IGNORECASE)


def own_pages(source: str, shell: str | None = None) -> int:
    """How many strings in a module's code open an HTML page (a doctype, ``<html>``, ``<head>`` or ``<body>``),
    outside the function named ``shell``: an f-string's literal parts read as one string, and a string in one of
    its fields, a nested f-string's among them, as a string of its own; a docstring is no page."""
    tree = ast.parse(source)
    skipped = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == shell:
            skipped |= {id(inner) for inner in ast.walk(node)}
        elif isinstance(node, ast.JoinedStr):
            skipped |= {id(part) for part in node.values if isinstance(part, ast.Constant)}  # its literal parts, read with it
    pages = 0
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.JoinedStr):
            text = "".join(part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        else:
            continue
        pages += bool(_OPENS_A_PAGE.search(text))
    return pages


def page_walk(app: Path) -> dict[str, int]:
    """Each module under ``app`` that builds HTML pages of its own, with how many: the mail module's shell aside, and
    no other module's function of that name."""
    found = {}
    for path in sorted(app.rglob("*.py")):
        if pages := own_pages(path.read_text(encoding="utf-8"), "_wrap_html" if path == app / "services" / "email_service.py" else None):
            found[path.relative_to(app.parent).as_posix()] = pages
    return found


def test_no_module_builds_a_page_of_its_own_outside_the_shell():
    found = page_walk(APP)
    assert own_pages(EMAIL_SERVICE.read_text(encoding="utf-8")) == 1, "the walk no longer finds the shell's own page"
    assert found == OWN_PAGES, (
        f"these modules build HTML pages of their own: {found}. Build mail through email_service's public functions, "
        "whose shell carries the header, and hold OWN_PAGES to what is left in the same diff"
    )


# Each way a module can open an HTML page, and the look-alikes that open none.
PAGES = [
    ("a page in a literal", 'P = "<html><body>x</body></html>"\n', None, 1),
    ("a page in an f-string, in capitals", 'P = f"<HTML lang=en>{x}"\n', None, 1),
    ("two pages in one module", 'A = "<html>a</html>"\nB = "<html>b</html>"\n', None, 2),
    ("a page in a function beside the shell", 'def _wrap_html(b):\n    return f"<html>{b}</html>"\n\n\ndef other():\n    return "<html>x"\n', "_wrap_html", 1),
    ("the shell's own page", 'def _wrap_html(b):\n    return f"<html>{b}</html>"\n', "_wrap_html", 0),
    ("a docstring that names a page", 'def f():\n    """Builds no <html> page."""\n    return 1\n', None, 0),
    ("a module's docstring that names a page", '"""Builds no <html> page."""\nP = 1\n', None, 0),
    ("a class's docstring that names a page", 'class C:\n    """Holds no <html> page."""\n', None, 0),
    ("a comment that names a page", "# <html>\nP = 1\n", None, 0),
    ("a tag that only starts like the page's", 'P = "<htmlx>"\n', None, 0),
    ("a page that opens with its doctype, head and body, and no html tag", 'P = "<!doctype html><head></head><body>x</body>"\n', None, 1),
    ("a page that opens with its body alone", 'P = "<body>x</body>"\n', None, 1),
    ("an f-string's page, counted once whatever its fields part", 'P = f"<html><head><title>{t}</title></head><body>{b}</body></html>"\n', None, 1),
    ("a page that opens with its doctype alone", 'P = "<!doctype html><p>x</p>"\n', None, 1),
    ("a page that opens with its head alone", 'P = "<head><title>x</title></head><p>x</p>"\n', None, 1),
    ("an f-string whose page opens past its first literal piece", 'P = f"<!-- built {when} --><html><body>{b}</body></html>"\n', None, 1),
    ("a page in a string inside an f-string's field", "P = f\"{'<html><body>' if full else ''}{b}\"\n", None, 1),
    ("a page in an f-string nested in another's field", "P = f\"{f'<html>{b}</html>' if full else b}\"\n", None, 1),
    ("a fragment with no page around it, which the sender check holds", 'P = "<p>Hi</p>"\n', None, 0),
    ("a tag that only starts like a body's", 'P = "<bodyx>"\n', None, 0),
]


@pytest.mark.parametrize("source, shell, pages", [case[1:] for case in PAGES], ids=[case[0] for case in PAGES])
def test_the_page_check_scores_every_planted_module(source, shell, pages):
    assert own_pages(source, shell) == pages


def test_the_page_walk_sets_aside_the_mail_modules_shell_alone(tmp_path):
    services = tmp_path / "app" / "services"
    services.mkdir(parents=True)
    shell = 'def _wrap_html(body):\n    return f"<html>{body}</html>"\n'
    (services / "email_service.py").write_text(shell, encoding="utf-8")
    (services / "recap_mail.py").write_text(shell, encoding="utf-8")  # a shell of its own, under the mail module's name
    assert page_walk(tmp_path / "app") == {"app/services/recap_mail.py": 1}


# The modules of backend/app that send mail, each with how many times it names a function that sends (``senders``)
# and what it sends. email_service builds its mail in the shell that carries the header, and the render holds every
# mail it sends through the transport to a page the shell built; its count holds a send the render does not record,
# through the queue or to the provider, to a look as well. The queue, the filing scan and the data-quality report send
# what it builds; contact.py builds two pages of its own, one to the person who wrote in (E56), and the admin and
# feedback routes send fragments. Equalities (lessons/test-allowlist-caps-are-equalities.md): a new sender, or a listed
# one that names a send once more, fails here until it sends through email_service or is listed with what it sends.
SENDERS = {
    "app/services/email_service.py": (10, "every mail it builds, in the shell, through the transport"),
    "app/services/notification_delivery_service.py": (1, "the filing alerts and digests email_service builds, held for delivery"),
    "app/services/filing_scan_service.py": (5, "the filing alerts and digests email_service builds, queued: three batches and two drains"),
    "app/services/data_quality_service.py": (1, "the data-quality report email_service builds, with its text copy"),
    "app/routers/contact.py": (2, "a notice to the team and a confirmation to the person who wrote in, pages of its own (E56)"),
    "app/routers/admin.py": (1, "an admin's test mail, a fragment, to the address the admin gives"),
    "app/routers/email.py": (1, "an admin's test mail, a fragment, to the address the admin gives"),
    "app/routers/feedback.py": (1, "a notice of beta feedback to the team, a fragment"),
}
# The functions that send a page or hand one on to be sent, by the module that holds them: the transport's, the mail
# module's hold of it (email_service imports send_email), and the delivery queue's, which take a page or send one. A
# module that binds one, or a module that holds one, holds it too (``_holders``).
_SENDS = {
    "app.services.resend_service": frozenset({"send_email"}),
    "app.services.email_service": frozenset({"send_email"}),
    "app.services.notification_delivery_service": frozenset({"create_batch", "replace_batch", "PreparedSend", "send_prepared", "drain"}),
}
_PROVIDER = frozenset({"RESEND_API_KEY", "RESEND_BASE_URL"})  # what a call of the provider itself needs


def _dotted(node: ast.AST) -> str | None:
    """A name or a chain of attributes on one, written out (``a.b.c``)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and (owner := _dotted(node.value)) is not None:
        return f"{owner}.{node.attr}"
    return None


def _module_name(path: Path, app: Path) -> str:
    """A module's dotted name, a package's ``__init__`` its package's."""
    parts = path.relative_to(app.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _module_named(owner: str, modules: dict[str, str], aliases: dict[str, str]) -> str:
    """A dotted name as the module it names, read as Python reads its attributes: its first name as the module binds
    it, else as a top-level package, then each attribute in turn, the module's own name for a module
    (``mailer.delivery``) else the module of that name below it, through any chain of them."""
    head, *rest = owner.split(".")
    named = modules.get(head, head)
    for part in rest:
        named = aliases.get(f"{named}.{part}", f"{named}.{part}")
    return named


def _holds(named: str, holders: dict[str, frozenset[str]]) -> bool:
    """Whether a module holds a function that sends, or is a package with one below it (``app.services``), whose
    name for that module, once it is imported, reads it."""
    return named in holders or any(key.startswith(f"{named}.") for key in holders)


def _held(node: ast.AST, modules: dict[str, str], holders: dict[str, frozenset[str]], aliases: dict[str, str]) -> frozenset[str]:
    """The functions that send held by the module a node names: through a name bound to it, by its dotted path, or
    through another module's name for it (``mailer.delivery``)."""
    owner = _dotted(node)
    return frozenset() if owner is None else holders.get(_module_named(owner, modules, aliases), frozenset())


def _bindings(
    tree: ast.Module, path: Path, app: Path, holders: dict[str, frozenset[str]], aliases: dict[str, str]
) -> tuple[set[str], dict[str, str]]:
    """The names a module binds to a function that sends, and to a module that holds one, with that module: imported
    by name or through a star import, and each name a binding hands one on to, a module's attribute among them."""
    functions: set[str] = set()
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update({alias.asname: alias.name for alias in node.names if alias.asname and _holds(alias.name, holders)})
        elif isinstance(node, ast.ImportFrom):
            module = _imported(node, path, app)
            for alias in node.names:
                # An import finds its module by its path, not its attributes, then the name in it: that module's own
                # name for a module, else the module of that name below it.
                if alias.name == "*":
                    functions |= holders.get(module, frozenset())
                    below = {key for key in [*holders, *aliases] if key.rpartition(".")[0] == module}
                    modules.update({key.rpartition(".")[2]: named for key in below if _holds(named := aliases.get(key, key), holders)})
                elif _holds(named := aliases.get(f"{module}.{alias.name}", f"{module}.{alias.name}"), holders):
                    modules[alias.asname or alias.name] = named
                elif alias.name in holders.get(module, ()):
                    functions.add(alias.asname or alias.name)
    while True:  # a name bound to one of those, or to a module's function that sends, holds what it holds
        grown = False
        for node in ast.walk(tree):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) and node.value else []
            value = _dotted(node.value) if targets else None
            for target in [t for t in targets if isinstance(t, ast.Name) and t.id not in functions and t.id not in modules]:
                if value in functions or (
                    isinstance(node.value, ast.Attribute) and node.value.attr in _held(node.value.value, modules, holders, aliases)
                ):
                    functions.add(target.id)
                    grown = True
                elif value is not None and _holds(_module_named(value, modules, aliases), holders):
                    modules[target.id] = _module_named(value, modules, aliases)
                    grown = True
        if not grown:
            return functions, modules


def _holders(trees: dict[Path, ast.Module], app: Path) -> tuple[dict[str, frozenset[str]], dict[str, str]]:
    """The modules that hold a function that sends, and each module's names for one. A module holds those ``_SENDS``
    names, and each under ``app`` holds each function that sends it binds, by import or by a binding, which it hands
    on to its importers, through any chain of them; one that binds a module that holds one holds it too. A module's
    name for a module (``app.services.mailer.delivery``) is that module, as Python binds it, so what it names
    is read through every module that holds it, however deep; each is recorded once, as it is first read, so a
    package that rebinds a name a module has read as the subpackage of that name keeps the subpackage."""
    holders: dict[str, frozenset[str]] = dict(_SENDS)
    aliases: dict[str, str] = {}
    while True:
        grown = False
        for path, tree in trees.items():
            name = _module_name(path, app)
            functions, modules = _bindings(tree, path, app, holders, aliases)
            for local, module in modules.items():
                if f"{name}.{local}" not in aliases:
                    aliases[f"{name}.{local}"] = module
                    grown = True
            if (functions or modules) and not (name in holders and functions <= holders[name]):
                holders[name] = holders.get(name, frozenset()) | frozenset(functions)
                grown = True
        if not grown:
            return holders, aliases


def senders(app: Path) -> dict[str, int]:
    """The modules under ``app`` that send mail, each with how many times it names a function that sends a page or
    hands one on (the transport's ``send_email``, which ``email_service`` holds under that name, and the delivery
    queue's), or the provider's key or address, which a call of the provider past the transport needs. A function
    counts read through a module that holds it, by a name bound to the module or its dotted path; imported from one,
    by name or through a star import; and through each name a binding hands it on to. A module holds each function
    it binds so, and each module that holds one, and hands them on to its importers; its name for a module is that
    module, and a package holds the modules below it, so a re-export, of a function or of a module
    (``mailer.delivery``, or ``relay.q`` through a module that binds ``relay``), counts through any chain of them, and
    so does a package imported above it (``from app import services``). A setting counts read as an attribute or
    named in a string, as ``getattr`` takes it. An import alone sends nothing, nor does a caught ``ResendError`` or an
    annotation; a name in a type alias or an ``isinstance`` check counts as a send would (asking). The transport and
    the settings that define the provider are not read."""
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(app.rglob("*.py"))}
    holders, aliases = _holders(trees, app)
    found: dict[str, int] = {}
    for path, tree in trees.items():
        if path in (app / "services" / "resend_service.py", app / "config.py"):
            continue
        functions, modules = _bindings(tree, path, app, holders, aliases)
        annotations = {
            id(inner)
            for node in ast.walk(tree)
            for annotation in (getattr(node, "annotation", None), getattr(node, "returns", None))
            if isinstance(annotation, ast.AST)
            for inner in ast.walk(annotation)
        }
        sends = 0
        for node in ast.walk(tree):
            if id(node) in annotations:
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in functions:
                sends += 1
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                sends += node.attr in _held(node.value, modules, holders, aliases) or node.attr in _PROVIDER
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                sends += node.value in _PROVIDER or "api.resend.com" in node.value
        if sends:
            found[path.relative_to(app.parent).as_posix()] = sends
    return found


def test_only_the_listed_modules_send_mail():
    found = senders(APP)
    held = {module: sends for module, (sends, _) in SENDERS.items()}
    assert set(found) == set(held), (
        f"the modules that send mail changed: {found}. Build mail through email_service's public functions, whose shell "
        "carries the header, or list the module in SENDERS with what it sends"
    )
    assert found == held, (
        f"a listed module names a function that sends a different number of times: {found}. Say in SENDERS what the "
        "new send sends, and hold its count to it"
    )


# Each way a module can send mail, with how many sends it names, and the look-alikes that send none.
SENDS = [
    ("the transport's function imported by name and called", 'from app.services.resend_service import send_email\nsend_email(html="<p>x</p>")\n', 1),
    ("the transport imported from its package, its function called", 'from app.services import resend_service\nresend_service.send_email(html="<p>x</p>")\n', 1),
    ("the transport by its dotted path", "import app.services.resend_service\napp.services.resend_service.send_email()\n", 1),
    ("the transport imported under another name", "import app.services.resend_service as mail\nmail.send_email()\n", 1),
    ("the transport's function through a relative import of a name", "from .resend_service import send_email\nsend_email()\n", 1),
    ("the transport through a relative import of the module", "from . import resend_service\nresend_service.send_email()\n", 1),
    ("the transport imported and called inside a function", "def f():\n    from app.services import resend_service\n    return resend_service.send_email()\n", 1),
    ("the transport's function imported from the mail module under another name", "from app.services.email_service import send_email as deliver\ndeliver()\n", 1),
    ("the transport's function imported from a package that re-exports it, and called", "from app.services import send_email\nsend_email()\n", 1, {"services/__init__.py": "from .resend_service import send_email\n"}),
    ("the transport's function read through a module that re-exports it", "from app.services import mailer\nmailer.send_email()\n", 1, {"services/mailer.py": "from app.services.resend_service import send_email\n"}),
    ("the transport's function through a chain of re-exports, renamed on the way, the later read first", "from app.services.dispatch import send_email\nsend_email()\n", 1, {"services/relay.py": "from app.services.resend_service import send_email as deliver\n", "services/dispatch.py": "from app.services.relay import deliver as send_email\n"}),
    ("the queue's names read through a module that star-imports them", "from app.services import mailer\nmailer.drain(db)\n", 1, {"services/mailer.py": "from app.services.notification_delivery_service import *\n"}),
    ("the transport's function read through the mail module", "from app.services import email_service\nemail_service.send_email(html='<p>x</p>')\n", 1),
    ("the transport's function read through the mail module's dotted path", "import app.services.email_service\napp.services.email_service.send_email()\n", 1),
    ("the transport's function read through a name bound to the mail module", "from app.services import email_service\nes = email_service\nes.send_email()\n", 1),
    ("the transport's function handed on under a name, then called", "from app.services.resend_service import send_email\nSEND = send_email\nSEND()\n", 2),
    ("two sends in one module, each counted", 'from app.services.resend_service import send_email\nsend_email(html="<p>a</p>")\nsend_email(html="<p>b</p>")\n', 2),
    ("the delivery queue imported whole, a batch made", 'from app.services import notification_delivery_service as delivery\ndelivery.create_batch(html="<p>x</p>")\n', 1),
    ("the delivery queue by its dotted path", "import app.services.notification_delivery_service\napp.services.notification_delivery_service.create_batch()\n", 1),
    ("the delivery queue through a relative import", "from . import notification_delivery_service\nnotification_delivery_service.send_prepared(p)\n", 1),
    ("the queue's batch, which takes a page, imported by name and called", 'from app.services.notification_delivery_service import create_batch\ncreate_batch(html="<p>x</p>")\n', 1),
    ("the queue's prepared send, imported by name", 'from app.services.notification_delivery_service import PreparedSend, send_prepared\nsend_prepared(PreparedSend(html="<p>x</p>"))\n', 2),
    ("the provider's key read past the transport, as a call of the provider needs", "from app.config import settings\nKEY = settings.RESEND_API_KEY\n", 1),
    ("the provider's address written out", 'URL = "https://api.resend.com/emails"\n', 1),
    ("the provider's host written out alone", 'HOST = "api.resend.com"\n', 1),
    ("the provider's address read past the transport", "from app.config import settings\nURL = settings.RESEND_BASE_URL\n", 1),
    ("the provider's key read through getattr", 'from app.config import settings\nKEY = getattr(settings, "RESEND_API_KEY")\n', 1),
    ("the queue's batch replaced through the module", 'from app.services import notification_delivery_service as delivery\ndelivery.replace_batch(db, html="<p>x</p>")\n', 1),
    ("the queue's batch imported by name from a package that re-exports it", "from app.services import create_batch\ncreate_batch()\n", 1, {"services/__init__.py": "from .notification_delivery_service import create_batch\n"}),
    ("the transport's names through a star import", 'from app.services.resend_service import *\nsend_email(html="<p>x</p>")\n', 1),
    ("the queue's names through a relative star import", "from .notification_delivery_service import *\ndrain(db)\n", 1),
    ("the transport's function read through its module and handed on under a name", "from app.services import resend_service\nSEND = resend_service.send_email\nSEND()\nSEND()\n", 3),
    ("the transport's function handed on under an annotated name", "from app.services import resend_service\nSEND: object = resend_service.send_email\nSEND()\n", 2),
    ("the queue's module handed on by its dotted path", "import app.services.notification_delivery_service\nq = app.services.notification_delivery_service\nq.create_batch()\n", 1),
    ("the transport's module read through a module that re-exports it", "from app.services.mailer import resend_service\nresend_service.send_email()\n", 1, {"services/mailer.py": "from app.services import resend_service\n"}),
    ("the queue's module read through a module that re-exports it under another name", "from app.services.mailer import delivery\ndelivery.create_batch()\n", 1, {"services/mailer.py": "from app.services import notification_delivery_service as delivery\n"}),
    ("the queue's module read through the re-exporting module's name for it", "from app.services import mailer\nmailer.delivery.create_batch()\n", 1, {"services/mailer.py": "from app.services import notification_delivery_service as delivery\n"}),
    ("the queue's module through the re-exporting module's dotted path", "import app.services.mailer\napp.services.mailer.delivery.drain(db)\n", 1, {"services/mailer.py": "from app.services import notification_delivery_service as delivery\n"}),
    ("the transport's module through a chain of two re-exports, renamed on the way", "from app.services.dispatch import transport\ntransport.send_email()\n", 1, {"services/relay.py": "from app.services import resend_service as transport\n", "services/dispatch.py": "from app.services.relay import transport\n"}),
    ("the transport's function read through a module that re-exports it, imported under another name", "import app.services.mailer as m\nm.send_email()\n", 1, {"services/mailer.py": "from app.services.resend_service import send_email\n"}),
    ("the transport's function through a star import of a module that re-exports it", "from app.services.mailer import *\nsend_email()\n", 1, {"services/mailer.py": "from app.services.resend_service import send_email\n"}),
    ("the transport's module through a star import of a module that re-exports it", "from app.services.mailer import *\nresend_service.send_email()\n", 1, {"services/mailer.py": "from app.services import resend_service\n"}),
    ("the transport's module bound to a name from the re-exporting module's name for it", "from app.services import mailer\ntransport = mailer.resend_service\ntransport.send_email()\n", 1, {"services/mailer.py": "from app.services import resend_service\n"}),
    ("the queue's module through a chain whose second module binds the first's name for it", "from app.services.dispatch import delivery\ndelivery.drain(db)\n", 1, {"services/relay.py": "from app.services import notification_delivery_service as q\n", "services/dispatch.py": "from app.services import relay\ndelivery = relay.q\n"}),
    ("the queue's module read through a module that another module re-exports, by that module's own name for it", "from app.services.dispatch import relay\nrelay.q.drain(db)\n", 1, {"services/relay.py": "from app.services import notification_delivery_service as q\n", "services/dispatch.py": "from app.services import relay\n"}),
    ("the transport read through its package, imported above it", "from app import services\nservices.resend_service.send_email()\n", 1),
    ("the transport read through its package imported under another name", "import app.services as s\ns.resend_service.send_email()\n", 1),
    ("the transport read through a name bound to its package", "import app.services\nsvc = app.services\nsvc.resend_service.send_email()\n", 1),
    ("the queue's module read two names past the module the reader binds, through a module that another re-exports", "from app.services import dispatch\ndispatch.relay.q.drain(db)\n", 1, {"services/relay.py": "from app.services import notification_delivery_service as q\n", "services/dispatch.py": "from app.services import relay\n"}),
    ("the queue's module read around a cycle of two modules that import each other", "from app.services.dispatch import relay\nrelay.dispatch.relay.q.drain(db)\n", 1, {"services/relay.py": "from app.services import dispatch\nfrom app.services import notification_delivery_service as q\n", "services/dispatch.py": "from app.services import relay\n"}),
    ("the transport's error imported by name, which sends nothing", "from app.services.resend_service import ResendError\n", 0),
    ("the transport imported for its error alone", "from app.services import resend_service\ntry:\n    pass\nexcept resend_service.ResendError:\n    pass\n", 0),
    ("the transport's function imported and never named", "from app.services.resend_service import send_email\n", 0),
    ("a public mail function imported by name and called", "from app.services.email_service import send_daily_digest\nsend_daily_digest()\n", 0),
    ("a public mail function read through the module", "from app.services import email_service\nemail_service.send_daily_digest()\n", 0),
    ("a request's flag named send_email", "class Invite:\n    send_email: bool = False\n\n\ndef f(payload):\n    return payload.send_email\n", 0),
    ("a module named like the transport", "import app.services.resend_service_stub\napp.services.resend_service_stub.send_email()\n", 0),
    ("the queue's click record, which sends nothing, imported by name", 'from app.services.notification_delivery_service import record_first_click\nrecord_first_click(db, "x", now)\n', 0),
    ("a function of another module's that shares the transport's name, which sends nothing", "from app.services import mailer\nmailer.send_email()\n", 0, {"services/mailer.py": "def send_email(to):\n    return to\n"}),
    ("the queue's prepared send in annotations alone", "from app.services.notification_delivery_service import PreparedSend\n\n\ndef f(p: PreparedSend) -> PreparedSend:\n    held: PreparedSend = p\n    return held\n", 0),
    ("the queue's prepared send in subscripted annotations alone", "from typing import Optional\n\nfrom app.services.notification_delivery_service import PreparedSend\n\n\ndef f(p: Optional[PreparedSend]) -> list[PreparedSend]:\n    return [p]\n", 0),
    ("the transport's error read through a module that re-exports the transport, which sends nothing", "from app.services.mailer import resend_service\ntry:\n    pass\nexcept resend_service.ResendError:\n    pass\n", 0, {"services/mailer.py": "from app.services import resend_service\n"}),
    ("the transport's error through a star import of a module that re-exports the transport, which sends nothing", "from app.services.mailer import *\ntry:\n    pass\nexcept resend_service.ResendError:\n    pass\n", 0, {"services/mailer.py": "from app.services import resend_service\n"}),
    ("the transport's error through a name bound to the re-exporting module's name for it, which sends nothing", "from app.services import mailer\ntransport = mailer.resend_service\nError = transport.ResendError\n", 0, {"services/mailer.py": "from app.services import resend_service\n"}),
    ("the queue's click record read through a module that another module re-exports, which sends nothing", "from app.services.dispatch import relay\nrelay.q.record_first_click(db, \"x\", now)\n", 0, {"services/relay.py": "from app.services import notification_delivery_service as q\n", "services/dispatch.py": "from app.services import relay\n"}),
    ("the queue's click record through a chain whose second module binds the first's name for it, which sends nothing", "from app.services.dispatch import delivery\ndelivery.record_first_click(db, \"x\", now)\n", 0, {"services/relay.py": "from app.services import notification_delivery_service as q\n", "services/dispatch.py": "from app.services import relay\ndelivery = relay.q\n"}),
    ("a public mail function read through its package, imported above it, which sends nothing", "from app import services\nservices.email_service.send_daily_digest()\n", 0),
    ("the transport's error read through its package, imported above it, which sends nothing", "from app import services\nE = services.resend_service.ResendError\n", 0),
]


@pytest.mark.parametrize("source, sends, beside", [(*case[1:3], case[3] if len(case) > 3 else {}) for case in SENDS], ids=[case[0] for case in SENDS])
def test_the_sender_check_scores_every_planted_module(tmp_path, source, sends, beside):
    services = tmp_path / "app" / "services"
    services.mkdir(parents=True)
    (services / "recap_mail.py").write_text(source, encoding="utf-8")
    for name, text in beside.items():  # a module beside it that re-exports a send, or holds a look-alike, and sends nothing itself
        (tmp_path / "app" / name).write_text(text, encoding="utf-8")
    assert senders(tmp_path / "app") == ({"app/services/recap_mail.py": sends} if sends else {})


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


def send_problems(html_sent: dict[str, list[str]], renders) -> list[str]:
    """Where a mail module's renders break the rule that each ``send_`` function sends mail and every mail it sends
    is a page the shell built, while a render or build function sends none."""
    problems = []
    sending = {name for name, sent in html_sent.items() if sent}
    if sending != {name for name in renders if name.startswith("send_")}:
        problems.append(
            f"these renders sent mail: {sorted(sending)}. Each send_ function sends what its render builds, and a "
            "render or build function returns its mail and sends none"
        )
    problems += [
        f"{name} sends mail that is no page the shell built, which no page rule here reads: build it with _wrap_html: "
        f"{html[:120]!r}"
        for name, sent in html_sent.items()
        for html in sent
        if not _PAGE.match(html)
    ]
    return problems


def test_every_mail_the_module_sends_is_a_page_the_shell_built(rendered):
    # The page check holds every other string of email_service.py from opening a page, so an HTML that opens the
    # shell's doctype is the shell's, and each page rule below reads it.
    problems = send_problems(rendered["html_sent"], RENDERS)
    assert not problems, "\n".join(problems)


# Each way a mail module's sends can break that rule, as stub modules the same render runs, and the stub that keeps
# it. Each binds the transport's send_email as email_service does; one reaches the transport itself.
_STUB = (
    "from app.services import resend_service\nfrom app.services.resend_service import send_email\n\n"
    "PAGE = '<!doctype html><html><body>x</body></html>'\n\n\n"
)
_RENDER_NOTE = "\n\ndef render_note():\n    return PAGE\n"
SENT = [
    # Broken.
    ("a send_ function that sends a fragment", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html='<p>x</p>')\n", {"send_note": [{"to": TO}]}, "no page the shell built"),
    ("a send_ function that sends a fragment holding a doctype past its start", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html='<p>x</p>' + PAGE)\n", {"send_note": [{"to": TO}]}, "no page the shell built"),
    ("a send_ function whose second send is a fragment", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=PAGE)\n    await send_email(to=[to], subject='s', html='<p>x</p>')\n", {"send_note": [{"to": TO}]}, "no page the shell built"),
    ("a send_ function whose second input sends a fragment", _STUB + "async def send_note(to, page):\n    await send_email(to=[to], subject='s', html=PAGE if page else '<p>x</p>')\n", {"send_note": [{"to": TO, "page": True}, {"to": TO, "page": False}]}, "no page the shell built"),
    ("a send_ function that sends a fragment through the transport itself, its error caught", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=PAGE)\n    try:\n        await resend_service.send_email(to=[to], subject='s', html='<p>x</p>')\n    except resend_service.ResendError:\n        pass\n", {"send_note": [{"to": TO}]}, "no page the shell built"),
    ("a render function that sends its page", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=PAGE)\n\n\nasync def render_note():\n    await send_email(to=[TO], subject='s', html=PAGE)\n    return PAGE\n\n\nTO = 'a@e.test'\n", {"send_note": [{"to": TO}], "render_note": [{}]}, "these renders sent mail"),
    ("a send_ function that sends nothing", _STUB + "async def send_note(to):\n    return PAGE\n" + _RENDER_NOTE, {"send_note": [{"to": TO}], "render_note": [{}]}, "these renders sent mail"),
    # Kept.
    ("a send_ function that sends the page its render builds", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=render_note())\n" + _RENDER_NOTE, {"send_note": [{"to": TO}], "render_note": [{}]}, None),
]


@pytest.fixture(scope="module")
def planted_sends() -> dict:
    run = subprocess.run(  # nosec B603: this file, run by this interpreter
        [sys.executable, __file__, "planted"], env={**os.environ, "PYTHONPATH": str(BACKEND)}, cwd=BACKEND,
        capture_output=True, text=True, timeout=300,
    )
    assert run.returncode == 0, f"the planted renders failed:\n{run.stderr[-3000:]}"
    return json.loads(run.stdout.splitlines()[-1])


def _planted_sends() -> dict[str, dict[str, list[str]]]:
    """In the render's own interpreter: the HTML each planted stub module sends, as the render records it."""
    import importlib
    import tempfile

    sent = {}
    with tempfile.TemporaryDirectory() as folder:
        sys.path.insert(0, folder)
        for index, (label, source, cases, _) in enumerate(SENT):
            (Path(folder) / f"planted_mail_{index}.py").write_text(source, encoding="utf-8")
            sent[label] = _render(cases, importlib.import_module(f"planted_mail_{index}"))["html_sent"]
    return sent


@pytest.mark.parametrize("label, cases, expected", [(case[0], *case[2:]) for case in SENT], ids=[case[0] for case in SENT])
def test_the_send_check_scores_every_planted_module(planted_sends, label, cases, expected):
    problems = send_problems(planted_sends[label], cases)
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"


def test_every_page_sent_keeps_the_headers_set_size_and_leaves_the_rest_to_the_view(rendered):
    problems = [f"{name}: {problem}" for name, page in _pages(rendered) for problem in text_size_problems(page)]
    assert not problems, "\n".join(sorted(set(problems)))


# How many long runs each render's pages print, page by page in the order of its inputs: the reader's name typed
# as an address, a company's name, a link with its token, a report's hashes and addresses. Held as it is, so an
# input that shortens every one a page prints fails here too, and a new render is listed with its own.
PRINTS_LONG_RUNS = {
    "render_welcome_email": [2], "send_waitlist_welcome_email": [2], "render_referral_success_email": [2],
    "send_referral_success_email": [2], "send_verification_email": [2], "send_invite_email": [1, 2],
    "send_password_reset_email": [2], "send_oauth_linked_email": [1], "send_account_exists_email": [1],
    "render_new_filing_alert": [2, 2, 2, 2, 2], "build_new_filing_alert": [2, 2, 2, 2, 2],
    "send_new_filing_alert": [2, 2, 2, 2, 2], "render_daily_digest": [4], "build_daily_digest": [4],
    "send_daily_digest": [4], "render_earnings_day_alert": [2, 2], "send_earnings_day_alert": [2, 2],
    "render_data_quality_report": [0, 4],
}


def _caller_values(value, path: str):
    """Each value an input hands in, with where: through its dicts and lists."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _caller_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _caller_values(item, f"{path}[{i}]")
    else:
        yield path, value


def test_the_inputs_hand_in_the_readers_name_and_each_link_at_their_real_lengths():
    # A report's run and artifact addresses are its own data, written at their real lengths.
    short = [
        f"{where} = {value!r}"
        for render, inputs in RENDERS.items()
        for i, kwargs in enumerate(inputs)
        for where, value in _caller_values(kwargs, f"{render}[{i}]")
        if (where.endswith(".name") and value != NAME)
        or (where.endswith(".to_email") and value != TO)
        or (where.endswith(".company_name") and value != COMPANY)
        or (where.rsplit(".", 1)[-1].endswith(("_link", "_url")) and value != LINK and ".report." not in where)
    ]
    unnamed = [
        render
        for render, inputs in RENDERS.items()
        if "name" in inspect.signature(getattr(email_service, render)).parameters
        and not any(kwargs.get("name") == NAME for kwargs in inputs)
    ]
    assert not short and not unnamed, (
        "an input that names the reader passes NAME, and every render that takes a name is given it once at least; one that "
        "addresses the mail passes TO, one that names a company passes COMPANY, and one that hands in a link passes LINK, so "
        "the lines that print them are held to the long-run rule at the lengths callers send:\n" + "\n".join(short + unnamed)
    )
    lengths = {"NAME": len(NAME), "TO": len(TO), "LINK's token": len(LINK.rsplit("=", 1)[-1]), "COMPANY's longest run": max(map(len, COMPANY.split()))}
    assert lengths == {"NAME": 34, "TO": 39, "LINK's token": 43, "COMPANY's longest run": 19}, (
        f"the inputs print each run at the length this file's comments and header give: {lengths}"
    )
    slots = {item.get("time") for kwargs in EARNINGS for item in kwargs["items"]}
    assert set(email_service._TIME_LABEL) <= slots, (
        "an input prints each time slot an earnings-day row can show, so each label is held to the long-run rule: "
        f"{sorted(set(email_service._TIME_LABEL) - slots)} printed by none"
    )


def test_every_long_run_a_page_sent_shows_can_break(rendered):
    pages = _pages(rendered)
    counts: dict[str, list[int]] = {}
    for name, page in pages:
        counts.setdefault(name, []).append(len(long_runs(page)))
    assert counts == PRINTS_LONG_RUNS, (
        f"the renders' pages print these numbers of long runs, page by page: {counts}. Hold PRINTS_LONG_RUNS to them, "
        "with inputs that print each such line at its real length"
    )
    problems = [f"{name}: {problem}" for name, page in pages for problem in long_run_problems(page)]
    assert not problems, "\n".join(sorted(set(problems)))


def test_every_page_sent_holds_its_width_on_a_phone_and_in_outlook(rendered):
    problems = [
        f"{name}: {problem}"
        for name, page in _pages(rendered)
        for problem in fixed_width_problems(page) + outlook_width_problems(page)
    ]
    assert not problems, "\n".join(sorted(set(problems)))


def test_every_page_sent_keeps_the_break_rule_out_of_its_tables(rendered):
    problems = [f"{name}: {problem}" for name, page in _pages(rendered) for problem in reach_problems(page)]
    assert not problems, "\n".join(sorted(set(problems)))


def test_every_page_sent_sets_the_shells_viewport_alone(rendered):
    shell = viewports(email_service._wrap_html("<p>Body</p>", preheader="The mail's own line."))
    assert shell == ["width=device-width, initial-scale=1"], f"the shell no longer sets the phone's own width: {shell}"
    problems = [f"{name}: {sets}" for name, page in _pages(rendered) if (sets := viewports(page)) != shell]
    assert not problems, (
        "a page sets a viewport other than the shell's, or another beside it, so a phone may lay it out wider than its "
        "screen and show its text at a fraction of its size:\n" + "\n".join(sorted(set(problems)))
    )


def test_the_earnings_day_rows_keep_a_two_word_slot_on_one_line():
    page, text = email_service.render_earnings_day_alert(
        name=None, items=[dict(ticker=f"T{n}", company_name="Acme", time=time) for n, time in enumerate(("bmo", "amc", "dmh"))]
    )
    for slot in ("·&nbsp;before&nbsp;open", "·&nbsp;after&nbsp;close", "·&nbsp;during market hours"):
        assert page.count(slot) == 1, (
            f"the row no longer prints {slot!r}: the middot stays with the slot, and a two-word slot keeps its words on one line"
        )
    for slot in ("(before open)", "(after close)", "(during market hours)"):
        assert slot in text, f"the plain text no longer reads {slot!r}"
    # The row's map and the plain text's name the same slots in the same words, so the inputs, which print each slot
    # _TIME_LABEL holds, print each the row can show.
    assert {key: html.unescape(label).replace("\xa0", " ") for key, label in email_service._TIME_LABEL_HTML.items()} == email_service._TIME_LABEL, (
        "the HTML row and the plain text name the same slots in the same words: keep _TIME_LABEL_HTML in step with _TIME_LABEL"
    )


def test_every_page_sent_takes_its_colours_from_the_tokens(rendered):
    problems = [f"{name}: {problem}" for name, page in _pages(rendered) for problem in colour_problems(page)]
    assert not problems, "\n".join(sorted(set(problems)))


# The preheader, as email_service._preheader opens <body> with it: the line an inbox lists beside the subject.
_OPENS_BODY = re.compile(r'<body\b[^>]*>\s*<div style="([^"]*)">(.*?)</div>', re.IGNORECASE | re.DOTALL)
_HIDDEN_DIV = re.compile(r'<div\b[^>]*\bstyle="[^"]*display\s*:\s*none', re.IGNORECASE)
# A scheme, a www. host, a host with a path, or an address. A bare host with no path passes: a company's name can
# be shaped like one ("Amazon.com, Inc.").
_LINK_OR_ADDRESS = re.compile(r"://|\bwww\.|\b[a-z0-9-]+\.[a-z]{2,}/|@", re.IGNORECASE)
# A bound this gate sets on a line, so that most phones' previews show it whole (F26 checks the inboxes it reaches).
PREHEADER_LIMIT = 90
# The fill, as React Email's preview component (6.11.3) repeats it after its line: one set of these characters,
# each a blank or nothing, for each character the line falls short of PREVIEW_LENGTH, so that in most previews the
# line is followed by blanks and not by the header's words. The set holds no direction mark, which spam filters
# such as rspamd score as hidden text (React Email 6.11.2's note).
FILL_SET = "&nbsp;&zwnj;&#8203;&zwj;&#65279;"
PREVIEW_LENGTH = 200
_FILL_RUN = re.compile(f"(?:{re.escape(FILL_SET)})+$")
# How React Email's preview component hides the line besides display:none, for a client that drops it.
REACT_EMAIL_HIDING = {"overflow": "hidden", "line-height": "1px", "opacity": "0", "max-height": "0", "max-width": "0"}


def _declared(style: str) -> dict[str, str]:
    """The value each property takes in an inline style, as a browser reads one: an important declaration over a
    normal one, among equals the last, and a comment is no declaration."""
    won: dict[str, tuple[bool, str]] = {}
    for item in tinycss2.parse_blocks_contents(style, skip_comments=True, skip_whitespace=True):
        if item.type == "declaration" and (item.lower_name not in won or item.important or not won[item.lower_name][0]):
            won[item.lower_name] = (item.important, tinycss2.serialize(item.value).strip().lower())
    return {name: value for name, (_, value) in won.items()}


def preheader_problems(page: str) -> list[str]:
    """Where a page breaks the preheader's rules (email_service._preheader). It opens <body> with one hidden line of
    the mail's own, so an inbox lists the mail by its own words and not by the header's. The line is plain text,
    PREHEADER_LIMIT characters at most, with no link or address (_LINK_OR_ADDRESS), since an inbox shows it before
    the mail is opened, a phone's lock screen among them. It is hidden as React Email hides it, with classic
    Outlook's mso-hide:all, each property read as a browser reads the style (_declared). The fill comes after it, a
    set of React Email's characters for each character the line falls short of PREVIEW_LENGTH, so in most previews
    the header's words do not follow the line."""
    opening = _OPENS_BODY.search(page)
    if not opening:
        return ["the page opens <body> with no preheader, so an inbox lists the mail by the header's words: hand "
                "_wrap_html the mail's own line"]
    style, inner = opening.groups()
    declared = _declared(html.unescape(style))
    problems = []
    if declared.get("display") != "none":
        problems.append("the preheader is not display:none, so the view shows it above the header")
    if declared.get("mso-hide") != "all":
        problems.append("the preheader is not mso-hide:all, so classic Outlook shows it above the header")
    if missing := [f"{name}:{value}" for name, value in REACT_EMAIL_HIDING.items() if declared.get(name) != value]:
        problems.append(
            f"the preheader is not hidden as React Email hides it ({'; '.join(missing)} missing), so a client that drops "
            "display:none shows it"
        )
    fill = _FILL_RUN.search(inner)
    if "<" in inner:
        problems.append("the preheader holds markup: its line is plain text, escaped as a unit")
    line = html.unescape(inner[: fill.start()] if fill else inner).strip()
    sets = (fill.end() - fill.start()) // len(FILL_SET) if fill else 0
    if not fill:
        problems.append(
            "the fill no longer follows the preheader's line: React Email's set, repeated, ends the preheader, so the "
            "header's words do not follow the line into the preview"
        )
    elif sets + len(line) < PREVIEW_LENGTH:
        problems.append(
            f"the fill no longer follows the preheader's line in full ({sets} sets after {len(line)} characters, short "
            f"of {PREVIEW_LENGTH}), so the header's words follow it into a preview that long"
        )
    if not re.search(r"\w", line):
        problems.append("the preheader's line is empty, so an inbox lists the mail by the header's words")
    if len(line) > PREHEADER_LIMIT:
        problems.append(f"the preheader's line runs to {len(line)} characters, past the {PREHEADER_LIMIT} this gate allows: {line!r}")
    if _LINK_OR_ADDRESS.search(line):
        problems.append(
            "the preheader's line carries a link or an address, which an inbox shows before the mail is opened, a phone's "
            f"lock screen among them: {line!r}"
        )
    hidden = len(_HIDDEN_DIV.findall(page))
    if hidden > 1:
        problems.append(f"the page holds {hidden} hidden lines: it holds one preheader, first in <body>")
    return problems


def test_every_page_sent_opens_with_a_line_of_its_own(rendered):
    problems = [f"{name}: {problem}" for name, page in _pages(rendered) for problem in preheader_problems(page)]
    assert not problems, "\n".join(sorted(set(problems)))


def test_a_preheader_escapes_what_a_caller_hands_in():
    # A company's name, a ticker and a form type are a caller's data, as EDGAR and the calendar send them.
    company, ticker, form = 'Tom & Jerry <a href="x">Inc</a>', "<i>T</i>", "<b>10-K</b>"
    pages = [
        email_service.render_new_filing_alert(name=None, company_name=company, ticker=ticker, filing_type=form, filing_date="2026-01-01", filing_id=1)[0],
        email_service.render_daily_digest(name=None, items=[dict(company_name=company, ticker=ticker, filing_type=form, filing_date="2026-01-01", filing_id=1)])[0],
        email_service.render_earnings_day_alert(name=None, items=[dict(ticker=ticker, company_name=company, time="bmo"), dict(ticker="B", time="amc")])[0],
        email_service.render_earnings_day_alert(name=None, items=[dict(ticker=ticker, company_name=company, time="bmo")])[0],
    ]
    problems = [problem for page in pages for problem in preheader_problems(page)]
    assert not problems, "a preheader carries what a caller hands in as text, escaped as a unit:\n" + "\n".join(problems)
    lines = [_preheader_line(page) for page in pages]
    assert company in lines[0] and ticker in lines[1] and form in lines[1] and ticker in lines[2] and company in lines[3], (
        f"each line reads what the caller handed in, escaped once and no more: {lines}"
    )


def _preheader_line(page: str) -> str:
    """A page's preheader line, as an inbox reads it: its text, the fill aside."""
    inner = _OPENS_BODY.search(page).group(2)
    fill = _FILL_RUN.search(inner)
    return html.unescape(inner[: fill.start()] if fill else inner).strip()


# Each mail's line, as the render's inputs give it: the words an inbox lists the mail by. A change to a line is
# a change to this list, read in review.
PREHEADER_LINES = {
    "render_welcome_email": ["You're number 3 on the list. Share your referral link to move up."],
    "render_referral_success_email": ["Someone joined with your referral link. You're now number 2."],
    "send_verification_email": ["Confirm your email address. The link works for 24 hours."],
    "send_invite_email": ["The private beta, with full Pro access and no card needed. The link works once."] * 2,
    "send_password_reset_email": ["Set a new password. The link works once, for one hour."],
    "send_oauth_linked_email": ["If this was you, there's nothing to do. If it wasn't, reset your password now."],
    "send_account_exists_email": ["You already have an account. Log in, or ignore this if it wasn't you."],
    "render_new_filing_alert": [f"{COMPANY} filed with the SEC on 2026-01-01."] * 5,
    "render_daily_digest": ["PVCT 10-K, PVCT 10-K and PVCT 10-K."],
    "render_earnings_day_alert": ["PVCT before open and BETA during market hours.", f"{COMPANY} reports after close."],
    "render_data_quality_report": ["This week's scan, each section with its count."] * 2,
}
# The eleven mails the module builds, each once: its render, or the send_ function that builds its page.
MAILS = (
    "render_welcome_email", "render_referral_success_email", "send_verification_email", "send_invite_email",
    "send_password_reset_email", "send_oauth_linked_email", "send_account_exists_email", "render_new_filing_alert",
    "render_daily_digest", "render_earnings_day_alert", "render_data_quality_report",
)
# A send_ or build_ function sends what its render builds.
PREHEADER_LINES |= {
    "send_waitlist_welcome_email": PREHEADER_LINES["render_welcome_email"],
    "send_referral_success_email": PREHEADER_LINES["render_referral_success_email"],
    "build_new_filing_alert": PREHEADER_LINES["render_new_filing_alert"],
    "send_new_filing_alert": PREHEADER_LINES["render_new_filing_alert"],
    "build_daily_digest": PREHEADER_LINES["render_daily_digest"],
    "send_daily_digest": PREHEADER_LINES["render_daily_digest"],
    "send_earnings_day_alert": PREHEADER_LINES["render_earnings_day_alert"],
}


def test_each_mail_lists_by_its_own_line(rendered):
    lines: dict[str, list[str]] = {}
    for name, page in _pages(rendered):
        lines.setdefault(name, []).append(_preheader_line(page))
    assert lines == PREHEADER_LINES, (
        f"the mails' preheader lines are now {lines}: hold PREHEADER_LINES to them in the diff that changes a line"
    )
    firsts = {mail: PREHEADER_LINES[mail][0] for mail in MAILS}
    assert len(set(firsts.values())) == len(MAILS), f"each mail lists by a line of its own: {firsts}"
    # The renders pass NAME as the reader's name, shaped like an address; no line prints any part of it.
    named = [line for found in lines.values() for line in found if NAME.split("@")[0] in line]
    assert not named, f"a preheader names no one, since a phone's lock screen shows it: {named}"


def test_a_preheader_lists_as_many_names_as_its_line_holds_then_how_many_more():
    listed = email_service._listed
    assert [listed(list("ABCDE")[:n]) for n in range(6)] == ["", "A", "A and B", "A, B and C", "A, B, C and D", "A, B, C, D and E"]
    tickers = [f"T{n:03d} 10-K" for n in range(50)]
    assert listed(tickers) == ", ".join(tickers[:6]) + ", T006 10-K and 43 more", "as many as 89 characters hold, then how many more"
    assert listed(["X" * 120, "B"]) == "X" * 120 + " and 1 more", "the first is named, however long"
    assert listed(list("ABCDE"), room=15) == "A, B and 3 more"


def test_a_long_list_keeps_its_line_and_a_company_alone_is_named():
    # Four companies reporting during market hours, as the calendar names them, and a digest of fifty filings.
    hours = [dict(ticker=ticker, company_name=COMPANY, time="dmh") for ticker in ("GOOGL", "AMZN", "MSFT", "AAPL")]
    digest = [dict(DIGEST_ITEM, ticker=f"T{n:03d}", filing_id=n) for n in range(50)]
    pages = [
        email_service.render_earnings_day_alert(name=None, items=hours)[0],
        email_service.render_daily_digest(name=None, items=digest)[0],
    ]
    problems = [problem for page in pages for problem in preheader_problems(page)]
    assert not problems, "\n".join(problems)
    assert _preheader_line(pages[0]) == "GOOGL during market hours, AMZN during market hours, MSFT during market hours and 1 more."
    assert _preheader_line(pages[1]).endswith("T006 10-K and 43 more.")
    # A company alone is named in full, since the subject names its ticker; with no slot, it reports today.
    alone = email_service.render_earnings_day_alert(name=None, items=[dict(ticker="PVCT", company_name=COMPANY)])[0]
    assert _preheader_line(alone) == f"{COMPANY} reports today."


def _opening(div: str) -> str:
    return f'<!doctype html><html><body style="margin:0;">{div}<table><tr><td>EarningsNerd</td></tr></table></body></html>'


_HIDES = "display:none;overflow:hidden;line-height:1px;opacity:0;max-height:0;max-width:0;mso-hide:all;"


def _hidden(line: str, fill: str | None = None, style: str = _HIDES) -> str:
    """A preheader as _preheader writes one: hidden, the line as markup, then its fill (by default, a set for each
    character the line falls short of PREVIEW_LENGTH)."""
    sets = PREVIEW_LENGTH - len(html.unescape(line))
    return f'<div style="{style}">{line}{FILL_SET * sets if fill is None else fill}</div>'


# Each way a page can break the preheader's rules, and the look-alikes that keep them.
PREHEADERS = [
    # Broken.
    ("no preheader", '<!doctype html><html><body style="margin:0;"><table><tr><td>EarningsNerd</td></tr></table></body></html>', "with no preheader"),
    ("the preheader after the header", f'<!doctype html><html><body><table><tr><td>EarningsNerd</td></tr></table>{_hidden("A line.")}</body></html>', "with no preheader"),
    ("a preheader the view shows", _opening(_hidden("A line.", style=_HIDES.replace("display:none;", ""))), "not display:none"),
    ("a preheader classic Outlook shows", _opening(_hidden("A line.", style=_HIDES.replace("mso-hide:all;", ""))), "not mso-hide:all"),
    ("a preheader a later display shows", _opening(_hidden("A line.", style=_HIDES + "display:block;")), "not display:none"),
    ("a preheader a later mso-hide shows", _opening(_hidden("A line.", style=_HIDES + "mso-hide:none;")), "not mso-hide:all"),
    ("a preheader hidden only by display:none", _opening(_hidden("A line.", style="display:none;mso-hide:all;")), "not hidden as React Email hides it"),
    ("a line without its fill", _opening(_hidden("A line.", fill="")), "the fill no longer follows"),
    ("a line with a fill one set short", _opening(_hidden("A line.", fill=FILL_SET * 192)), "the fill no longer follows"),
    ("a line whose fill comes before it", _opening(f'<div style="{_HIDES}">{FILL_SET * 193}A line.</div>'), "the fill no longer follows"),
    ("a line with the old fill", _opening(_hidden("A line.", fill="&zwnj;&nbsp;" * 120)), "the fill no longer follows"),
    ("a fill with the direction marks", _opening(_hidden("A line.", fill="&nbsp;&zwnj;&#8203;&zwj;&lrm;&rlm;&#65279;" * 193)), "the fill no longer follows"),
    ("a line that holds markup", _opening(_hidden("<b>Acme</b> filed it.")), "holds markup"),
    ("an empty line", _opening(_hidden("")), "line is empty"),
    ("a line of punctuation", _opening(_hidden(". ")), "line is empty"),
    ("a line past the limit", _opening(_hidden("x" * 91)), "runs to 91 characters"),
    ("a line with a link", _opening(_hidden("Reset it at https://e.test/r?t=abc")), "carries a link or an address"),
    ("a line with a www host", _opening(_hidden("Read it at www.earningsnerd.io")), "carries a link or an address"),
    ("a line with a bare host and a path", _opening(_hidden("Reset it at earningsnerd.io/r?t=abc")), "carries a link or an address"),
    ("a line with an address", _opening(_hidden("Sent to a@e.test")), "carries a link or an address"),
    ("a second preheader", _opening(_hidden("A line.") + _hidden("Another.")), "2 hidden lines"),
    # Kept.
    ("the shell's own preheader", email_service._wrap_html("<p>Body</p>", preheader="The mail's own line."), None),
    ("a line with markup's characters, escaped", _opening(_hidden("Tom &amp; Jerry &lt;TJ&gt; filed it.")), None),
    ("a line at the limit", _opening(_hidden("x" * 90)), None),
    ("a company's name shaped like a host", _opening(_hidden("Amazon.com, Inc. filed with the SEC on 2026-01-01.")), None),
    ("a line with a longer fill", _opening(_hidden("A line.", fill=FILL_SET * 195)), None),
    ("a line whose style is spaced as written", _opening(_hidden("A line.", style="display: none; overflow: hidden; line-height: 1px; opacity: 0; max-height: 0; max-width: 0; mso-hide: all;")), None),
    ("a display:none that an important declaration keeps", _opening(_hidden("A line.", style=_HIDES.replace("display:none;", "display:none !important;") + "display:block;")), None),
]


@pytest.mark.parametrize("page, expected", [case[1:] for case in PREHEADERS], ids=[case[0] for case in PREHEADERS])
def test_the_preheader_check_scores_every_planted_page(page, expected):
    problems = preheader_problems(page)
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"


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


def test_the_planted_lists_keep_their_counts():
    """Each list's cases that must fail and that must pass. Equalities, not floors, so a case dropped after one
    is added still fails (lessons/test-allowlist-caps-are-equalities.md): change a count in the diff that adds or
    drops a case."""
    counts = {
        "PAGES": (sum(case[-1] > 0 for case in PAGES), sum(case[-1] == 0 for case in PAGES)),
        "REACHES": (sum(case[-1] is True for case in REACHES), sum(case[-1] is False for case in REACHES)),
        "SENDS": (sum(case[2] > 0 for case in SENDS), sum(case[2] == 0 for case in SENDS)),
        "ADDRESSES": (sum(isinstance(case[-1], str) for case in ADDRESSES), sum(case[-1] is None for case in ADDRESSES)),
        "SENT": (sum(isinstance(case[-1], str) for case in SENT), sum(case[-1] is None for case in SENT)),
        "PREHEADERS": (sum(isinstance(case[-1], str) for case in PREHEADERS), sum(case[-1] is None for case in PREHEADERS)),
    }
    assert counts == {
        "PAGES": (12, 8), "REACHES": (10, 4), "SENDS": (50, 18), "ADDRESSES": (63, 9), "SENT": (7, 1), "PREHEADERS": (21, 7),
    }, "a planted case was added or dropped: keep these counts equal to the lists in the same diff"
    for name, cases in (
        ("PAGES", PAGES), ("REACHES", REACHES), ("SENDS", SENDS), ("ADDRESSES", ADDRESSES), ("SENT", SENT), ("PREHEADERS", PREHEADERS),
    ):
        labels = [case[0] for case in cases]
        assert len(set(labels)) == len(labels), f"each case {name} plants has a name of its own"


if __name__ == "__main__":  # the renders, in an interpreter of their own (the mail fixture and the planted stubs')
    print(json.dumps(_planted_sends() if sys.argv[1:] == ["planted"] else _render(RENDERS)))
