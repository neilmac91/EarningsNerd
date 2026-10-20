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
returns. A page, as ``_wrap_html`` builds it, is read as its markup; any other string (a text part, a subject) as
markup and as the text it is, as a client shows a text part. In them it reads:
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
``email_service`` or is listed. Every send hands the transport a text part beside its page (planted in ``SENT``
too). Planted modules score each check. What it cannot see:
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
- mail built or sent outside ``email_service``, in the modules ``SENDERS`` lists: ``routers/contact.py``'s
  confirmation (E56) and the internal admin and team notices, which send no text part of their own, and the
  page and text part ``data_quality_service.run_and_email`` hands the transport, which the render here checks
  as ``render_data_quality_report`` returns them.

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

The preheader is the one text a page hides (E110): ``mail_styles.hidden_text_problems``, planted in
``HIDDEN_TEXTS``, finds every other way a page hides text from its reader or a spam filter reads as hidden, in a
browser's view, as rspamd reads the page, and in classic Outlook's view: an element laid out nowhere or that skips
its content, an opacity under 0.1, a box rspamd reads as off the page, a box that clips its overflow to under
4 px, ``visibility:hidden`` (on a box above, as rspamd reads it), a font size under 4 px (em at 16 px as rspamd
reads it), a colour that is transparent or too like the ground behind it, and ``mso-hide:all``; it refuses what it
does not model or resolve, a ``var()`` or ``calc()`` among the values, ``position``, the transforms, masks and
filters among the properties, and a page whose tree a browser builds otherwise than rspamd's HTML parser does. Its
planted cases were each scored offline against rspamd 4.2.2's own counts and against whether Chromium paints the
text. Each page once hid a plain-text copy of its mail, which took most of them past rspamd's HIDDEN_TEXT floor of
200 hidden characters (``rules/html.lua``; measured with rspamd 4.2.2 on production-shaped mails: the account
mails, the welcome and the referral, and a digest or an earnings alert of several companies). That copy is now the
mail's text part, which a client shows in place of the page and a spam filter compares with it: every mail carries
one, each ``send_`` function handing it to the transport as ``text=`` and each render or build function returning
it after its page, and it says what its page says (``text_part_problems``, planted in ``TEXT_PARTS``): the words
the page shows below its header (``mail_styles.shown_text``), save the line under a button that offers its link to
copy (``PAGE_ONLY``), every link the page carries written out, no address the page does not carry, the page's last
line last, and no markup or character reference, since a client shows the text as written. What it cannot see:
whether the text part's words come in the page's order; a word the page and the text part each say in another
sentence; and text a ``<style>`` block hides, which the page rules refuse.
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
import tinyhtml5

from app.services import email_service
from tests.support.mail_styles import (
    colour_problems,
    fixed_width_problems,
    hidden_text_problems,
    long_run_problems,
    long_runs,
    outlook_width_problems,
    reach_problems,
    shown_text,
    spamassassin_contrast_problems,
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
    and as the text it is, as a client shows a text part, so a text part's <https://...> is read too."""
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
    sent_text: list[object] = []

    async def _record(to, subject, html, *args, **kwargs):
        sent.extend(_strings([to, subject, html, list(args), kwargs]))
        sent_html.append(html)
        sent_text.append(kwargs.get("text"))
        return {"id": "msg_test"}

    out: dict[str, list[str]] = {}
    html_sent: dict[str, list[str]] = {}
    text_sent: dict[str, list[object]] = {}
    mails: dict[str, list[tuple[str, object]]] = {}  # each mail a function sends or returns, as (page, text part)
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
                text_sent.setdefault(name, []).extend(sent_text)
                pages = [part for part in result if isinstance(part, str) and _PAGE.match(part)] if isinstance(result, tuple) else []
                # A render or build function returns its text part last, after its page.
                mails.setdefault(name, []).extend([*zip(sent_html, sent_text), *((pages[0], result[-1]) for _ in pages[:1])])
                sent.clear()
                sent_html.clear()
                sent_text.clear()
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
        "text_sent": text_sent,
        "mails": mails,
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
    "app/services/data_quality_service.py": (1, "the data-quality report email_service builds, its page and text part"),
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


def send_problems(html_sent: dict[str, list[str]], text_sent: dict[str, list[object]], renders) -> list[str]:
    """Where a mail module's renders break the rule that each ``send_`` function sends mail and every mail it sends
    is a page the shell built with a text part beside it, while a render or build function sends none."""
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
    problems += [
        f"{name} sends a page with no text part, so the provider builds one from the page, its preheader and header "
        "among it, and a spam filter compares the two: hand send_email the mail's text= (email_service._wrap_text)"
        for name, sent in text_sent.items()
        for text in sent
        if not (isinstance(text, str) and text.strip())
    ]
    return problems


def test_every_mail_the_module_sends_is_a_page_the_shell_built(rendered):
    # The page check holds every other string of email_service.py from opening a page, so an HTML that opens the
    # shell's doctype is the shell's, and each page rule below reads it.
    problems = send_problems(rendered["html_sent"], rendered["text_sent"], RENDERS)
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
    ("a send_ function that sends its page with no text part", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=PAGE)\n", {"send_note": [{"to": TO}]}, "with no text part"),
    ("a send_ function that hands in a text part of None", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=PAGE, text=None)\n", {"send_note": [{"to": TO}]}, "with no text part"),
    ("a send_ function that hands in a blank text part", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=PAGE, text=' \\n ')\n", {"send_note": [{"to": TO}]}, "with no text part"),
    ("a send_ function whose second send has no text part", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=PAGE, text='Hi.')\n    await resend_service.send_email(to=[to], subject='s', html=PAGE)\n", {"send_note": [{"to": TO}]}, "with no text part"),
    # Kept.
    ("a send_ function that sends the page its render builds, with its text part", _STUB + "async def send_note(to):\n    await send_email(to=[to], subject='s', html=render_note(), text='Hi.')\n" + _RENDER_NOTE, {"send_note": [{"to": TO}], "render_note": [{}]}, None),
]


@pytest.fixture(scope="module")
def planted_sends() -> dict:
    run = subprocess.run(  # nosec B603: this file, run by this interpreter
        [sys.executable, __file__, "planted"], env={**os.environ, "PYTHONPATH": str(BACKEND)}, cwd=BACKEND,
        capture_output=True, text=True, timeout=300,
    )
    assert run.returncode == 0, f"the planted renders failed:\n{run.stderr[-3000:]}"
    return json.loads(run.stdout.splitlines()[-1])


def _planted_sends() -> dict[str, dict[str, dict[str, list]]]:
    """In the render's own interpreter: the HTML and the text part each planted stub module sends, as the render
    records them."""
    import importlib
    import tempfile

    sent = {}
    with tempfile.TemporaryDirectory() as folder:
        sys.path.insert(0, folder)
        for index, (label, source, cases, _) in enumerate(SENT):
            (Path(folder) / f"planted_mail_{index}.py").write_text(source, encoding="utf-8")
            render = _render(cases, importlib.import_module(f"planted_mail_{index}"))
            sent[label] = {"html": render["html_sent"], "text": render["text_sent"]}
    return sent


@pytest.mark.parametrize("label, cases, expected", [(case[0], *case[2:]) for case in SENT], ids=[case[0] for case in SENT])
def test_the_send_check_scores_every_planted_module(planted_sends, label, cases, expected):
    problems = send_problems(planted_sends[label]["html"], planted_sends[label]["text"], cases)
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
    for slot in ("· before open", "· after close", "· during market hours"):
        assert text.count(f"reports today {slot}") == 1, f"the text part no longer reads {slot!r} after its row's words"
    # The row's map and the plain text's name the same slots in the same words, so the inputs, which print each slot
    # _TIME_LABEL holds, print each the row can show.
    assert {key: html.unescape(label).replace("\xa0", " ") for key, label in email_service._TIME_LABEL_HTML.items()} == email_service._TIME_LABEL, (
        "the HTML row and the plain text name the same slots in the same words: keep _TIME_LABEL_HTML in step with _TIME_LABEL"
    )


def test_every_page_sent_takes_its_colours_from_the_tokens(rendered):
    problems = [f"{name}: {problem}" for name, page in _pages(rendered) for problem in colour_problems(page)]
    assert not problems, "\n".join(sorted(set(problems)))


def test_spamassassin_reads_no_text_on_a_page_sent_as_too_like_its_ground(rendered):
    problems = [f"{name}: {problem}" for name, page in _pages(rendered) for problem in spamassassin_contrast_problems(page)]
    assert not problems, (
        "SpamAssassin reads a text on a page in an ink too like its ground, which it scores as hidden text "
        "(HTML_FONT_LOW_CONTRAST) though its reader sees it plainly; it reads a ground from a style's background-color "
        "alone (E125):\n" + "\n".join(sorted(set(problems)))
    )


def _contrast_page(fragment: str) -> str:
    """A page around ``fragment``, which opens its own <body> where it starts with one, and is a page itself where it
    starts with a doctype."""
    if fragment.lstrip().startswith("<!doctype"):
        return fragment
    return f"<!doctype html><html><head></head>{'' if fragment.startswith('<body') else '<body>'}{fragment}</body></html>"


# Each way SpamAssassin can read a text in an ink too like its ground, each form the reader refuses, and the look-alikes
# it reads as clear of the ground. Each broken and kept page is scored with SpamAssassin 4.0.0's own HTML parser
# (tasks/review-evidence/e125-mail-spam-scores-2026-10-19/), which reads each as the reader does.
CONTRASTS = [
    # Broken.
    ("the button's sage in the background shorthand, on white", '<a href="https://e.test/v" style="display:inline-block;background:#4F7A63;color:#FFFFFF;">Verify my email</a>', "too like its ground"),
    ("the button's sage in the background shorthand, on the page's cream", '<table role="presentation" bgcolor="#F4F3EE" style="background-color:#F4F3EE;"><tr><td><a href="https://e.test/v" style="background:#4F7A63;color:#FFFFFF;">Verify my email</a></td></tr></table>', "too like its ground"),
    ("a ground in the background shorthand on a div", '<div style="background:#1A1A17;"><span style="color:#FBFAF6;">Pale words.</span></div>', "too like its ground"),
    ("a cell's ground in its bgcolor alone", '<table><tr><td bgcolor="#1A1A17"><span style="color:#FBFAF6;">Pale words.</span></td></tr></table>', "too like its ground"),
    ("a table's ground in its bgcolor alone", '<table bgcolor="#1A1A17"><tr><td><span style="color:#FBFAF6;">Pale words.</span></td></tr></table>', "too like its ground"),
    ("a row's ground in its bgcolor alone", '<table><tr bgcolor="#1A1A17"><td><span style="color:#FBFAF6;">Pale words.</span></td></tr></table>', "too like its ground"),
    ("a link's ground in a bgcolor", '<a href="https://e.test/v" bgcolor="#4F7A63" style="color:#FFFFFF;">Verify</a>', "too like its ground"),
    ("a marquee's bgcolor, on a tag it reads none of", '<marquee bgcolor="#1A1A17"><span style="color:#FBFAF6;">Pale words.</span></marquee>', "too like its ground"),
    ("a marquee left open in a cell, which a cell's start closes, as it reads no tag of one", '<table style="color:#FFFFFF;"><tr><td style="background-color:#000000;"><marquee>Pale on black.<td>Pale on white.</td></tr></table>', "too like its ground"),
    ("a body's ground in its style", '<body style="background-color:#1A1A17;"><p style="color:#FBFAF6;">Pale words.</p>', "too like its ground"),
    ("a body's ground in its bgcolor", '<body bgcolor="#1A1A17"><p style="color:#FBFAF6;">Pale words.</p>', "too like its ground"),
    ("a heading's ground, whose style it does not read", '<h2 style="background-color:#1A1A17;"><span style="color:#FBFAF6;">Pale heading.</span></h2>', "too like its ground"),
    ("an emphasis's ground, whose style it does not read", '<em style="background-color:#1A1A17;"><span style="color:#FBFAF6;">Pale words.</span></em>', "too like its ground"),
    ("a background-color spaced before its colon", '<div style="background-color :#1A1A17;"><span style="color:#FBFAF6;">Pale words.</span></div>', "too like its ground"),
    ("a heading's ink, unread, on a dark ground it reads", '<div style="background-color:#000000;"><h2 style="color:#FFFFFF;">Pale heading.</h2></div>', "too like its ground"),
    ("a color spaced before its colon, on a dark ground", '<div style="background-color:#000000;"><span style="color :#FFFFFF;">Pale words.</span></div>', "too like its ground"),
    ("a big's style, which it does not read, on a dark ground", '<div style="background-color:#000000;"><big style="color:#FFFFFF;">Pale words.</big></div>', "too like its ground"),
    ("a font's colour", '<font color="#FFFFFF">Pale words.</font>', "too like its ground"),
    ("a body's text colour", '<body text="#FFFFFF"><p>Pale words.</p>', "too like its ground"),
    ("a basefont's colour, where it sets no size", '<basefont color="#FFFFFF"><p>Pale words.</p>', "too like its ground"),
    ("a header cell's ink, read as a cell's", '<table><tr><th style="color:#FFFFFF;">Pale heading.</th></tr></table>', "too like its ground"),
    ("the page's cream as ink on white", '<span style="color:#F4F3EE;">Cream words.</span>', "too like its ground"),
    ("an ink just under 12 from its ground", '<div style="background-color:#000000;"><span style="color:#0F0F0F;">Near-black words.</span></div>', "too like its ground"),
    ("an ink of the ground's own colour", '<div style="background-color:#4F7A63;"><span style="color:#4F7A63;">Sage on sage.</span></div>', "too like its ground"),
    ("a style's later color over its earlier", '<div style="background-color:#000000;"><span style="color:#FFFFFF;color:#000000;">Black words.</span></div>', "too like its ground"),
    ("a style's later background-color over its earlier", '<div style="background-color:#000000;background-color:#FFFFFF;"><span style="color:#FFFFFF;">Pale words.</span></div>', "too like its ground"),
    ("inherit, which keeps the ink below", '<span style="color:#FFFFFF;"><span style="color:inherit;">Pale words.</span></span>', "too like its ground"),
    ("!important alone, which keeps the ink below", '<div style="background-color:#000000;"><span style="color:!important;">Black words.</span></div>', "too like its ground"),
    ("two styles, of which it reads the first", '<span style="color:#FFFFFF;" style="color:#1A1A17;">Pale words.</span>', "too like its ground"),
    ("a span written closed, which it holds open", '<span style="color:#FFFFFF;"/><p>Pale words.</p>', "too like its ground"),
    ("a span left open in a cell, which the next cell's start leaves open", '<table><tr><td style="background-color:#000000;"><span style="color:#FFFFFF;">Pale on black.<td style="background-color:#FFFFFF;">Pale on white.</td></tr></table>', "too like its ground"),
    ("a row's start, which closes the cells and the row before it to the table's ground", '<table style="background-color:#000000;"><tr><td style="background-color:#FFFFFF;">Black on white.<tr><td>Black on black.</td></tr></table>', "too like its ground"),
    ("a body's ink, which its end tag leaves open", '<body text="#FFFFFF"></body><p>Pale words after the body.</p>', "too like its ground"),
    ("a tag, an attribute and a declaration in capitals", '<SPAN STYLE="COLOR:#FFFFFF;">Pale words.</SPAN>', "too like its ground"),
    ("an unquoted style", "<span style=color:#FFFFFF>Pale words.</span>", "too like its ground"),
    ("a style in curly quotes, which it reads as straight ones", "<span style=\u201ccolor:#FFFFFF;\u201d>Pale words.</span>", "too like its ground"),
    ("a declaration after a newline", '<span style="\ncolor:#FFFFFF;">Pale words.</span>', "too like its ground"),
    ("a zero-width space, which counts as text", '<span style="color:#FFFFFF;">&#8203;</span>', "too like its ground"),
    ("a no-break space by its number, which counts as text", '<span style="color:#FFFFFF;">&#160;</span>', "too like its ground"),
    ("a no-break space as itself, which counts as text", '<span style="color:#FFFFFF;">\u00a0</span>', "too like its ground"),
    ("a no-break space by its name and then by its number, the second of which counts as text", '<span style="color:#FFFFFF;">&nbsp;&#160;</span>', "too like its ground"),
    ("a name a browser decodes as a tab, which it reads as written", '<span style="color:#FFFFFF;">&Tab;</span>', "too like its ground"),
    ("a block Outlook's conditional comments reveal to every other client", '<!--[if !mso]><!--><span style="color:#FFFFFF;">Pale words.</span><!--<![endif]-->', "too like its ground"),
    ("a noscript's markup, which it reads", '<noscript><span style="color:#FFFFFF;">Pale words.</span></noscript>', "too like its ground"),
    # Refused.
    ("a short hex", '<span style="color:#FFF;">Pale words.</span>', "does not read as SpamAssassin reads it"),
    ("a colour's name", '<span style="color:white;">Pale words.</span>', "does not read as SpamAssassin reads it"),
    ("rgb()", '<span style="color:rgb(255,255,255);">Pale words.</span>', "does not read as SpamAssassin reads it"),
    ("a colour with !important after it, which it reads as an invalid colour", '<span style="color:#FFFFFF !important;">Pale words.</span>', "does not read as SpamAssassin reads it"),
    ("a ground's name", '<div style="background-color:black;"><span style="color:#FFFFFF;">Pale on black.</span></div>', "does not read as SpamAssassin reads it"),
    ("a font's colour by name", '<font color="white">Pale words.</font>', "does not read as SpamAssassin reads it"),
    ("a body's text colour in a short hex", '<body text="#FFF"><p>Words.</p>', "does not read as SpamAssassin reads it"),
    ("a style written with a character reference", '<span style="color:&#35;FFFFFF;">Pale words.</span>', "written with a character reference"),
    ("a font's colour written with a character reference", '<font color="&#35;FFFFFF">Pale words.</font>', "written with a character reference"),
    ("a basefont's size written with a character reference, which the standard library decodes and it does not", '<basefont size="&Tab;3" color="#FFFFFF"><p>Pale words.</p>', "written with a character reference"),
    ("a title", "<title>A title.</title><p>Words.</p>", "reads as raw text"),
    ("a textarea", "<textarea>Words.</textarea>", "reads as raw text"),
    ("an xmp", '<xmp><span style="color:#FFFFFF;">Pale words.</span></xmp>', "reads as raw text"),
    ("a plaintext", "<plaintext>Words.", "reads as raw text"),
    ("a listing", "<listing>Words.</listing>", "reads as raw text"),
    ("an iframe", "<iframe>Words.</iframe>", "reads as raw text"),
    ("a noembed", "<noembed>Words.</noembed>", "reads as raw text"),
    ("a noframes", "<noframes>Words.</noframes>", "reads as raw text"),
    ("a script written closed", "<script/><p>Words.</p>", "raw text"),
    ("a script, whose text it passes over", '<span style="color:#FFFFFF;"><script>var words = 1;</script></span>', "raw text"),
    ("a style block, whose text it passes over", '<span style="color:#FFFFFF;"><style>p { margin: 0; }</style></span>', "raw text"),
    ("a no-break space in a style, which it reads as a space", '<div style="background-color:#1A1A17;"><span style="color:#FBFAF6;\u00a0color:#1A1A17;">Words.</span></div>', "past ASCII"),
    ("a Kelvin sign in a property's name, which it reads as a k", '<div style="bac\u212aground-color:#000000;"><span style="color:#FFFFFF;">Pale on black.</span></div>', "past ASCII"),
    ("a no-break space before the / that closes a span, which it reads as a space, so it holds the span open", '<span style="color:#FFFFFF;"><span\u00a0/></span>Pale words.</span>', "tag's name"),
    ("an end tag whose name holds a no-break space", '<span style="color:#1A1A17;">Ink words.</span\u00a0><p>Words.</p>', "tag's name"),
    ("a basefont's size in a digit past ASCII, which it reads as a digit", '<basefont size="\u0663" color="#FFFFFF"><p>Pale words.</p>', "size holds a character past ASCII"),
    ("a comment closed by -- >, where it ends one", '<p>Words.</p><!-- a note -- > <span style="color:#FFFFFF;">Pale words.</span> -->', "with an error"),
    ("a comment closed by --!>", '<p>Words.</p><!-- a note --!> <span style="color:#FFFFFF;">Pale words.</span> -->', "with an error"),
    ("an end tag holding an attribute", '<span style="color:#1A1A17;">Ink words.</span class="x"><p>Words.</p>', "with an error"),
    ("a vertical tab between a tag's name and its attribute", '<span\x0bstyle="color:#FFFFFF;">Pale words.</span>', "with an error"),
    ("a / between a tag's name and its attribute", '<span/style="color:#FFFFFF;">Pale words.</span>', "with an error"),
    ("a reference by number with no semicolon", '<span style="color:#FFFFFF;">&#32 </span>', "with an error"),
    ("a reference by number past Unicode's last code point", '<span style="color:#FFFFFF;">&#x110000;</span>', "with an error"),
    ("a reference by number twenty digits long, past Unicode's last code point too", '<span style="color:#FFFFFF;">&#99999999999999999999;</span>', "with an error"),
    ("a bare ampersand before a word", '<p>R&D words.</p>', "with an error"),
    ("a CDATA section", '<![CDATA[<span style="color:#FFFFFF;">Pale words.</span>]]>', "a marked section"),
    ("a block Outlook's marked section reveals", '<![if !mso]><span style="color:#FFFFFF;">Pale words.</span><![endif]>', "a marked section"),
    # Kept.
    ("the shell's own page", email_service._wrap_html("<p>Body</p>", preheader="The mail's own line."), None),
    ("the button's sage in background-color, on the page's cream", '<table role="presentation" bgcolor="#F4F3EE" style="background-color:#F4F3EE;"><tr><td><a href="https://e.test/v" style="display:inline-block;background-color:#4F7A63;color:#FFFFFF;">Verify my email</a></td></tr></table>', None),
    ("the panel's ground in bgcolor and the shorthand, unread under its ink", '<table bgcolor="#FBFAF6" style="background:#FBFAF6;color:#1A1A17;"><tr><td>Ink on the panel.</td></tr></table>', None),
    ("a body's ground, unread under the default ink", '<body style="background-color:#F4F3EE;"><p>Black on the page.</p>', None),
    ("a table's ground", '<table style="background-color:#000000;"><tr><td><span style="color:#FFFFFF;">Pale on black.</span></td></tr></table>', None),
    ("a row's ground", '<table><tr style="background-color:#000000;"><td><span style="color:#FFFFFF;">Pale on black.</span></td></tr></table>', None),
    ("a cell's ground", '<table><tr><td style="background-color:#000000;"><span style="color:#FFFFFF;">Pale on black.</span></td></tr></table>', None),
    ("a div's ground", '<div style="background-color:#000000;"><span style="color:#FFFFFF;">Pale on black.</span></div>', None),
    ("a paragraph's ground", '<p style="background-color:#000000;"><span style="color:#FFFFFF;">Pale on black.</span></p>', None),
    ("a span's ground", '<span style="background-color:#000000;color:#FFFFFF;">Pale on black.</span>', None),
    ("a link's ground", '<a href="https://e.test/v" style="background-color:#000000;color:#FFFFFF;">Pale on black.</a>', None),
    ("a ground in capitals", '<div style="BACKGROUND-COLOR:#000000;"><span style="color:#FFFFFF;">Pale on black.</span></div>', None),
    ("an ink just over 12 from its ground", '<div style="background-color:#000000;"><span style="color:#111111;">Near-black words.</span></div>', None),
    ("a style's later color, clear of the ground", '<div style="background-color:#000000;"><span style="color:#000000;color:#FFFFFF;">Pale on black.</span></div>', None),
    ("inherit, which keeps a clear ink", '<div style="background-color:#000000;"><span style="color:#FFFFFF;"><span style="color:inherit;">Pale on black.</span></span></div>', None),
    ("two styles, the first clear", '<span style="color:#1A1A17;" style="color:#FFFFFF;">Ink words.</span>', None),
    ("a cell's start, which closes the font and the cell before it", '<table><tr><td style="background-color:#000000;"><font color="#FFFFFF">Pale on black.<td style="background-color:#FFFFFF;">Black on white.</td></tr></table>', None),
    ("a row's start, which closes the fonts, the cells and the row before it", '<table><tr style="background-color:#000000;"><td><font color="#FFFFFF">Pale on black.<tr style="background-color:#FFFFFF;"><td>Black on white.</td></tr></table>', None),
    ("a header cell's end tag, which closes it as a cell's", '<table><tr><th style="background-color:#000000;"><span style="color:#FFFFFF;">Pale on black.</th><td style="background-color:#FFFFFF;">Black on white.</td></tr></table>', None),
    ("an end tag, which closes every element open above its own", '<div style="color:#FFFFFF;"><span style="background-color:#000000;">Pale on black.</div><p style="background-color:#FFFFFF;">Black on white.</p>', None),
    ("a stray end tag, which closes nothing", '<div style="background-color:#000000;"></span><span style="color:#FFFFFF;">Pale on black.</span></div>', None),
    ("a basefont that sets a size, and no colour", '<div style="background-color:#000000;color:#FFFFFF;"><basefont size="3" color="#000000"><p>Pale on black.</p></div>', None),
    ("a namespaced tag, which it passes over", '<div style="background-color:#000000;color:#FFFFFF;"><o:p style="color:#000000;">Pale on black.</o:p></div>', None),
    ("a no-break space by its name alone, which it reads as a space", '<span style="color:#FFFFFF;">&nbsp;&nbsp;</span>', None),
    ("an A with a circumflex before a no-break space, which it takes out as one", '<span style="color:#FFFFFF;">\u00c2\u00a0</span>', None),
    ("a tab by its number, which it reads as one", '<span style="color:#FFFFFF;">&#9;</span>', None),
    ("whitespace alone", '<span style="color:#FFFFFF;"> \t\n\f </span>', None),
    ("a comment, which holds no text", '<span style="color:#FFFFFF;"><!-- Pale words. --></span>', None),
    ("classic Outlook's conditional comment, which holds no text", '<span style="color:#FFFFFF;"><!--[if mso]>Pale words.<![endif]--></span>', None),
]


@pytest.mark.parametrize("page, expected", [(_contrast_page(case[1]), case[2]) for case in CONTRASTS], ids=[case[0] for case in CONTRASTS])
def test_the_contrast_check_scores_every_planted_page(page, expected):
    problems = spamassassin_contrast_problems(page)
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"


# The preheader, as email_service._preheader opens <body> with it: the line an inbox lists beside the subject.
_OPENS_BODY = re.compile(r'<body\b[^>]*>\s*<div style="([^"]*)">(.*?)</div>', re.IGNORECASE | re.DOTALL)
_HIDDEN_DIV = re.compile(r'<div\b[^>]*\bstyle="[^"]*display\s*:\s*none', re.IGNORECASE)
# A scheme, a www. host, a host with a path, or an address. A bare host with no path passes: a company's name can
# be shaped like one ("Amazon.com, Inc.").
_LINK_OR_ADDRESS = re.compile(r"://|\bwww\.|\b[a-z0-9-]+\.[a-z]{2,}/|@", re.IGNORECASE)
# A bound this gate sets on a line, so that most phones' previews show it whole (unchecked in a real inbox).
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


# The one text a page hides is its preheader (E110). Each page once hid a plain-text copy of its mail too, in a
# <pre style="display:none">, and on the account mails that copy and the preheader passed rspamd's HIDDEN_TEXT
# floor of 200 hidden characters (rules/html.lua); the copy now goes to the provider as the mail's text part.
def _without_preheader(page: str) -> str:
    """The page with its preheader taken out, which ``preheader_problems`` holds: the one text a page may hide."""
    opening = _OPENS_BODY.search(page)
    if not opening:
        return page
    start = opening.start() + opening.group(0).index("<div")
    return page[:start] + page[opening.end():]


def test_every_page_hides_no_text_but_its_preheader(rendered):
    problems = [
        f"{name}: {problem}" for name, page in _pages(rendered) for problem in hidden_text_problems(_without_preheader(page))
    ]
    assert not problems, (
        "a page hides text besides its preheader, which its reader never sees and a spam filter such as rspamd scores "
        "as hidden text (HIDDEN_TEXT, from 200 characters): show it, or send it in the mail's text part:\n"
        + "\n".join(sorted(set(problems)))
    )


def _hiding(fragment: str) -> str:
    """A page with a preheader, then ``fragment`` in a cell on the panel's ground, in the panel's ink."""
    return (
        f'<!doctype html><html><body style="background-color:#F4F3EE;">{_hidden("A line of its own.")}'
        '<table role="presentation"><tr><td style="background:#FBFAF6;color:#1A1A17;font-size:16px;">'
        f"<p>Words the reader sees.</p>{fragment}</td></tr></table></body></html>"
    )


# Each way a page can hide text from its reader, in a browser, in classic Outlook's view or as rspamd reads it, each form
# the reader reads stricter than a browser and each it refuses, and the look-alikes that show the text or hide nothing a
# filter counts, on each side of each floor.
HIDDEN_TEXTS = [
    # Broken: hidden in a browser.
    ("a hidden plain-text copy, as _hidden_text appended one", '<pre style="display:none">Hi there, a copy of the text part.</pre>', "laid out nowhere"),
    ("a second hidden line", '<div style="display:none">A second line no one sees.</div>', "laid out nowhere"),
    ("display:none, important over a later display", '<p style="display:none !important;display:block">Hidden still.</p>', "laid out nowhere"),
    ("a cell set to display:none", '<table><tr><td style="display:none">A hidden cell.</td></tr></table>', "laid out nowhere"),
    ("the hidden attribute", "<span hidden>A hidden span.</span>", "laid out nowhere"),
    ("a popover no script opens", "<div popover>Popover words.</div>", "laid out nowhere"),
    ("a box laid out as a table's column, whose content a browser does not render", '<div style="display:table-column">Column words.</div>', "display:table-column, a table's column"),
    ("a box laid out as a table's column group", '<div style="display:table-column-group">Group words.</div>', "display:table-column-group"),
    ("an SVG's title, a tooltip a browser does not lay out", '<svg width="10" height="10"><title>A tooltip of words.</title></svg>', "laid out nowhere"),
    ("hidden until found", '<div hidden="until-found">Found only by a search.</div>', "skips its content"),
    ("content-visibility:hidden", '<div style="content-visibility:hidden">Skipped content.</div>', "skips its content"),
    ("visibility:hidden", '<p style="visibility:hidden">Invisible words.</p>', "visibility:hidden"),
    ("visibility:collapse", '<p style="visibility:collapse">Collapsed words.</p>', "visibility:collapse, which hides all it holds whatever a box below sets"),
    ("a hidden parent's own words beside a child it shows", '<p style="visibility:hidden"><span style="visibility:visible">Shown.</span> Not shown.</p>', "visibility:hidden"),
    ("visibility:hidden on a box that sets a display", '<p style="visibility:hidden;display:block">Hidden words.</p>', "it is visibility:hidden"),
    ("a collapsed row's cell set visible again, which a browser removes with its row", '<table><tr style="visibility:collapse;display:table-row"><td style="visibility:visible">Collapsed row words.</td></tr></table>', "visibility:collapse, which hides all it holds whatever a box below sets"),
    ("a collapsed row group's cell set visible again", '<table><tbody style="visibility:collapse;display:table-row-group"><tr><td style="visibility:visible">Collapsed group words.</td></tr></tbody></table>', "visibility:collapse, which hides all it holds whatever a box below sets"),
    ("a row that inherits a collapse, its cell set visible again", '<div style="visibility:collapse;display:block"><table><tr><td style="visibility:visible">Inherited collapse words.</td></tr></table></div>', "visibility:collapse, which hides all it holds whatever a box below sets"),
    ("a column that inherits a collapse, under a row group set visible again", '<div style="visibility:collapse;display:block"><table><col><tbody style="visibility:visible"><tr><td>Collapsed column words.</td></tr></tbody></table></div>', "visibility:collapse, which hides all it holds whatever a box below sets"),
    ("opacity:0", '<p style="opacity:0">Words at no opacity.</p>', "opacity:0"),
    ("opacity as a percentage", '<p style="opacity:0%">Words at no opacity.</p>', "opacity:0%"),
    ("opacities that multiply under the floor of 0.1, each box over it", '<div style="opacity:0.2"><p style="opacity:0.12">Twice faded.</p></div>', "opacities multiply to 0.024, under 0.1"),
    ("opacity:inherit, which multiplies the parent's again", '<div style="opacity:0.15"><p style="opacity:inherit">Twice faded.</p></div>', "opacities multiply to 0.0225, under 0.1"),
    ("two opacities of 0.3, whose product, 0.09, sits under the floor though the ink paints apart from the ground", '<div style="opacity:0.3"><p style="opacity:0.3">Faint words.</p></div>', "opacities multiply to 0.09, under 0.1"),
    ("an opacity of 0.05 rspamd skips after a second semicolon, which a browser paints as a ghost of the ink", '<p style="opacity:1;;opacity:0.05">Faded words.</p>', "opacities multiply to 0.05, under 0.1"),
    ("a pale ink at an opacity of 0.4, over the floor, which paints it too like the ground", '<p style="opacity:0.4;color:#E5E7EB">Pale words.</p>', "painted at the opacity of 0.4 its boxes multiply to, is too like the ground"),
    ("ink at an alpha of 0.3 under a box at 0.3, which paints the pixels two opacities of 0.3 paint, under the floor", '<div style="opacity:0.3"><p style="color:rgba(26,26,23,0.3)">Faint words.</p></div>', "paint its ink at 0.09, under 0.1"),
    ("ink at an alpha of 0.09 under no faded box, the ghost a box at 0.09 paints, under the floor", '<p style="color:rgba(26,26,23,0.09)">Faint words.</p>', "colour's alpha paints its ink at 0.09, under 0.1"),
    ("font-size:0", '<p style="font-size:0">Words at no size.</p>', "font size is 0px"),
    ("a font size of 2 px", '<p style="font-size:2px">Words too small to read.</p>', "font size is 2px"),
    ("a font just under 4 px", '<p style="font-size:3.9px">Words too small to read.</p>', "font size is 3.9px, under 4 px"),
    ("font:0/0 a, the shorthand", '<p style="font:0/0 a">Words at no size.</p>', "font size is 0px"),
    ("a font shorthand after the longhand", '<p style="font-size:16px;font:2px Arial">Words too small to read.</p>', "font size is 2px"),
    ("a size a parent at 0 hands down", '<div style="font-size:0"><span>Inherited words.</span></div>', "font size is 0px"),
    ("font-size:unset of a parent at 0", '<div style="font-size:0"><p style="font-size:unset">Inherited words.</p></div>', "font size is 0px"),
    ("font:inherit of a parent at 0", '<div style="font-size:0"><p style="font:inherit">Inherited words.</p></div>', "font size is 0px"),
    ("a percentage of the parent's size", '<p style="font-size:10%">Words at a tenth.</p>', "font size is 1.6px"),
    ("an em of a small parent", '<div style="font-size:4px"><span style="font-size:0.5em">Half of four.</span></div>', "font size is 2px"),
    ("smaller under a parent at 4.5 px", '<div style="font-size:4.5px"><p style="font-size:smaller">A size smaller.</p></div>', "font size is 3.75px"),
    ("<font size> under a style that sets a size of 0", '<font size="7" style="font-size:0">Legacy words.</font>', "font size is 0px"),
    ("ruby text at the half size a browser's own sheet gives it", '<div style="font-size:7px"><ruby>A<rt>Fine print in a ruby.</rt></ruby></div>', "font size is 3.5px"),
    ("<small> under a parent at 4.5 px, set smaller by a browser's own sheet", '<div style="font-size:4.5px"><small>Fine print.</small></div>', "font size is 3.75px"),
    ("<h6> under a parent at 5.9 px, at the 0.67em a browser's own sheet gives it", '<div style="font-size:5.9px"><h6>A small heading.</h6></div>', "font size is 3.953px"),
    ("font-size:revert on a <sub>, back to a browser's own smaller size", '<div style="font-size:4.5px"><sub style="font-size:revert">Fine print.</sub></div>', "font size is 3.75px"),
    ("a tenth of a form control's 13.333 px, whatever its parent's", '<div style="font-size:48px"><button><span style="font-size:10%">Pressed words.</span></button></div>', "font size is 1.33333px"),
    ("max-height:0 under overflow:hidden, as a preheader hides", '<p style="max-height:0;overflow:hidden">Clipped words.</p>', "max-height:0 under overflow-y:hidden"),
    ("height:0 under overflow:hidden", '<p style="height:0;overflow:hidden">Clipped words.</p>', "(height:0 under overflow-y:hidden"),
    ("a box 1 px wide that clips", '<p style="width:1px;overflow:hidden">Clipped words.</p>', "width:1px under overflow-x:hidden"),
    ("a box that clips at 3.5 px", '<p style="max-height:3.5px;overflow:hidden">Clipped words.</p>', "max-height:3.5px under overflow-y:hidden"),
    ("a max of 0 that caps a height in percent the reader does not resolve", '<p style="height:50%;max-height:0;overflow:hidden">Clipped words.</p>', "max-height:0 under overflow-y:hidden"),
    ("overflow-y:clip under a zero height", '<p style="height:0;overflow-y:clip">Clipped words.</p>', "height:0 under overflow-y:clip"),
    ("a scroll box of no height", '<p style="height:0;overflow:auto">Clipped words.</p>', "height:0 under overflow-y:auto"),
    ("overflow-x:hidden, beside which a visible axis clips as auto", '<p style="overflow-x:hidden;height:0">Clipped words.</p>', "height:0 under overflow-y:auto"),
    ("the shorthand's visible second word beside a hidden first", '<p style="overflow:hidden visible;height:0">Clipped words.</p>', "height:0 under overflow-y:auto"),
    ("overflow-y:hidden on a box of no width", '<p style="overflow-y:hidden;width:0">Clippedwordsthatrunlong.</p>', "width:0 under overflow-x:auto"),
    ("a floated span that clips at no height", '<span style="float:left;height:0;overflow:hidden">Clipped words.</span>', "height:0 under overflow-y:hidden"),
    ("a span a flex container lays out as a block, that clips at no height", '<div style="display:flex"><span style="height:0;overflow:hidden">Clipped words.</span></div>', "height:0 under overflow-y:hidden"),
    ("a span a flex container lays out through display:contents, that clips at 2 px", '<div style="display:flex"><div style="display:contents"><span style="overflow:hidden;height:2px">Flex item words.</span></div></div>', "height:2px under overflow-y:hidden"),
    ("a cell its width attribute clips", '<table style="table-layout:fixed;width:1px"><tr><td width="1" style="overflow:hidden">Clipped cell words.</td></tr></table>', 'width="1" under overflow-x:hidden'),
    ("max-block-size:0 under overflow:scroll", '<p style="max-block-size:0;overflow:scroll">Clipped words.</p>', "max-block-size:0 under overflow-y:scroll"),
    ("the overflow shorthand's second word", '<p style="overflow:visible hidden;max-height:0">Clipped words.</p>', "max-height:0 under overflow-y:hidden"),
    ("a transparent colour", '<p style="color:transparent">Clear words.</p>', "transparent"),
    ("rgba at no alpha", '<p style="color:rgba(26,26,23,0)">Clear words.</p>', "transparent"),
    ("the panel's colour on the panel", '<p style="color:#FBFAF6">White on white.</p>', "its colour is too like the ground"),
    ("a colour all but the ground's", '<p style="color:#FAF9F5">Near white on white.</p>', "its colour is too like the ground"),
    ("ink on a ground of ink", '<table><tr><td bgcolor="#1A1A17"><span style="color:#1A1A17">Dark on dark.</span></td></tr></table>', "its colour is too like the ground"),
    ("a named colour on its own ground", '<div style="background-color:white"><p style="color:white">Named white.</p></div>', "its colour is too like the ground"),
    ("the background shorthand's colour as the ground", '<div style="background:#123456"><p style="color:#123456">Blue on blue.</p></div>', "its colour is too like the ground"),
    ("panel ink on a ground of 3% black, laid over the panel", '<div style="background:rgba(0,0,0,0.03)"><p style="color:#FBFAF6">White on white.</p></div>', "its colour is too like the ground"),
    ("a transparent background over a dark ground", '<div style="background:#000000"><p style="background-color:transparent;color:#000000">Dark on dark.</p></div>', "its colour is too like the ground"),
    ("panel ink on a div whose bgcolor a browser ignores", '<div bgcolor="#123456"><p style="color:#FBFAF6">White on white.</p></div>', "its colour is too like the ground"),
    ("<font color> on the panel", '<font color="#FBFAF6">Legacy white.</font>', "its colour is too like the ground"),
    ("color:inherit of the panel's colour", '<div style="color:#FBFAF6"><p style="color:inherit">Inherited white.</p></div>', "its colour is too like the ground"),
    ("color:currentcolor of the panel's colour", '<div style="color:#FBFAF6"><p style="color:currentcolor">Inherited white.</p></div>', "its colour is too like the ground"),
    ("color:initial, black, on a black ground", '<div style="background:#000000"><p style="color:initial">Black on black.</p></div>', "its colour is too like the ground"),
    ("a link in a browser's blue on a ground of that blue", '<div style="background:#0000EE"><a href="https://e.test/x">A link</a></div>', "its colour is too like the ground"),
    ("a colour on a translucent ground a browser lays over a dark one", '<div style="background:#1A1A17"><div style="background:rgba(251,250,246,0.5)"><p style="color:#8A8A86">Mid on mid.</p></div></div>', "its colour is too like the ground"),
    ("a <font color> HTML parses without its #", '<font color="FBFAF6">Legacy white.</font>', "its colour is too like the ground"),
    ("a cell's bgcolor HTML parses without its #", '<table><tr><td bgcolor="1A1A17"><span style="color:#1A1A17">Dark on dark.</span></td></tr></table>', "its colour is too like the ground"),
    ("a hidden run of controls rspamd counts", '<p style="display:none">\u0085\u0085\u001c\u001d</p>', "laid out nowhere"),
    ("a column group laid out as one, a later display a browser drops aside", '<div style="display:table-column-group;display:bogus">Group words.</div>', "is display:table-column-group, a table's column"),
    ("a colour's name with a Kelvin sign, which a browser does not read as black", '<div style="color:#FBFAF6"><p style="color:blac\u212a">Pale words.</p></div>', "its colour is too like the ground"),
    # Broken: hidden in classic Outlook's view.
    ("mso-hide:all, which classic Outlook hides", '<div style="mso-hide:all">Words Outlook drops.</div>', "mso-hide:all"),
    ("a hidden line inside Outlook's conditional comment", '<!--[if mso]><div style="display:none">Outlook only, hidden.</div><![endif]-->', "laid out nowhere"),
    # Broken: hidden as rspamd reads it, shown in a browser or refused there.
    ("a child shown again under a hidden parent", '<div style="visibility:hidden"><span style="visibility:visible">Shown again.</span></div>', "rspamd reads <div> as visibility:hidden"),
    ("visibility after a display, which rspamd applies last", '<div style="display:block;visibility:hidden"><span style="visibility:visible">Shown again.</span></div>', "rspamd reads <div> as visibility:hidden"),
    ("a second display rspamd keeps where the first stood", '<div style="display:none;visibility:hidden;display:block"><span style="visibility:visible">Shown again.</span></div>', "rspamd reads <div> as visibility:hidden"),
    ("visibility:visible after hidden, which rspamd does not read", '<p style="visibility:hidden;visibility:visible">Shown in a browser.</p>', "rspamd reads <p> as visibility:hidden"),
    ("the hidden attribute over a display the page sets", '<p hidden style="display:block">Shown in a browser.</p>', "carries the hidden attribute"),
    ("a size of 4.3 px a browser shows and rspamd reads at 16 px an em", '<div style="font-size:18px"><p style="font-size:0.24em">Small words.</p></div>', "rspamd reads its font size as 3px"),
    ("ex, which rspamd reads at 8 px", '<div style="font-size:20px"><p style="font-size:0.45ex">Small words.</p></div>', "rspamd reads its font size as 3px"),
    ("a keyword size rspamd does not read, under a parent at 2 px", '<div style="font-size:2px"><p style="font-size:medium">Words at medium.</p></div>', "rspamd reads its font size as 2px"),
    ("font-size:initial, which rspamd does not read, under a parent at 0", '<div style="font-size:0"><p style="font-size:initial">Words at medium.</p></div>', "rspamd reads its font size as 0px"),
    ("<font size>, which rspamd does not read, under a style at 0", '<p style="font-size:0"><font size="3">Legacy words.</font></p>', "rspamd reads its font size as 0px"),
    ("<h1> under a parent at 2 px, 4 px a browser's way and 2 px rspamd's", '<div style="font-size:2px"><h1>A heading.</h1></div>', "rspamd reads its font size as 2px"),
    ("a height rspamd reads as 0, at 16 px an em, which a browser's 5 px clip refuses", '<p style="font-size:100px;height:0.05em;overflow:hidden">Clipped words.</p>', "rspamd reads height as 0"),
    ("a colour attribute rspamd reads over the style", '<p><span color="#FBFAF6" style="color:#1A1A17">Ink in a browser.</span></p>', "rspamd reads its colour as too like the ground"),
    ("a bgcolor on a div, which rspamd reads", '<div bgcolor="#1A1A17"><p style="color:#1A1A17">Ink on the panel.</p></div>', "rspamd reads its colour as too like the ground"),
    ("a 4-digit hex rspamd does not read, leaving the panel's colour above it", '<div style="color:#FBFAF6"><p style="color:#1118">Grey in a browser.</p></div>', "rspamd reads its colour as too like the ground"),
    ("a hidden copy at opacity 0.05", '<pre style="opacity:0.05">Hi there, a copy of the text part.</pre>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("opacity just under rspamd's floor of 0.1", '<p style="opacity:0.09">Words all but clear.</p>', "opacity:0.09, under 0.1, which rspamd reads"),
    ("a percentage under the floor", '<p style="opacity:5%">Words all but clear.</p>', "opacity:5%, under 0.1, which rspamd reads"),
    ("an opacity rspamd reads last, importance aside", '<p style="opacity:1 !important;opacity:0.05">Faded words.</p>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("a height rspamd reads last, importance aside", '<p style="height:40px !important;height:0;overflow:hidden">Clipped words.</p>', "rspamd reads height as 0 under overflow:hidden"),
    ("a min height that opens a clip rspamd reads at no height", '<p style="height:0;min-height:40px;overflow:hidden">A box min-height opens.</p>', "rspamd reads height as 0 under overflow:hidden"),
    ("a height rspamd hands down to a box that clips", '<div style="height:0"><p style="overflow:hidden">Clipped words.</p></div>', "rspamd reads height as 0 under overflow:hidden"),
    ("a width rspamd hands down to a span that clips", '<span style="width:0"><span style="overflow:hidden">Clipped words.</span></span>', "rspamd reads width as 0 under overflow:hidden"),
    ("a max height rspamd reads at 16 px an em, which a browser's 5 px clip refuses", '<p style="font-size:100px;max-height:0.05em;overflow:hidden">Clipped words.</p>', "rspamd reads height as 0 under overflow:hidden"),
    ("a height rspamd caps at a max of 0%, which a browser reads as none in a cell", '<p style="height:20px;max-height:0%;overflow:hidden">Clipped words.</p>', "rspamd reads height as 0 under overflow:hidden"),
    ("a font-size rspamd reads over a later font shorthand", '<p style="font-size:2px;font:16px Arial">Words.</p>', "rspamd reads its font size as 2px"),
    ("the overflow shorthand's last word, which rspamd reads alone", '<p style="overflow:visible clip;width:0">Words.</p>', "rspamd reads width as 0 under overflow:clip"),
    ("a size rspamd keeps in whole px, under a percentage", '<div style="font-size:4.9px"><p style="font-size:90%">Small words.</p></div>', "rspamd reads its font size as 3px"),
    ("a percentage rspamd cuts to a whole number", '<div style="font-size:13px"><p style="font-size:30.9%">Small words.</p></div>', "rspamd reads its font size as 3px"),
    ("a font shorthand's size rspamd reads at 16 px an em", '<div style="font-size:18px"><p style="font:0.24em Arial">Small words.</p></div>', "rspamd reads its font size as 3px"),
    ("the last font shorthand's size, importance aside", '<p style="font:16px Arial !important;font:2px Arial">Words.</p>', "rspamd reads its font size as 2px"),
    ("a colour rspamd reads in a font shorthand", '<p style="font:16px white">Words in black.</p>', "rspamd reads its colour as too like the ground"),
    ("a color attribute of transparent over the style", '<p><span color="transparent" style="color:#1A1A17">Ink in a browser.</span></p>', "rspamd reads its colour as transparent"),
    ("a faint ground rspamd reads as opaque", '<div style="background:rgba(26,26,23,0.05)"><p style="color:#1A1A17">Ink words.</p></div>', "rspamd reads its colour as too like the ground"),
    ("an rgb() of four components, which rspamd does not read", '<div style="color:#FBFAF6"><p style="color:rgb(26 26 23 / 0.5)">Ink if read.</p></div>', "rspamd reads its colour as too like the ground"),
    ("hwb(), which rspamd does not read", '<div style="color:#FBFAF6"><p style="color:hwb(60 9% 90%)">Ink if read.</p></div>', "rspamd reads its colour as too like the ground"),
    ("a hue in degrees, which rspamd does not read", '<div style="color:#FBFAF6"><p style="color:hsl(60deg 6% 10%)">Ink in a browser.</p></div>', "rspamd reads its colour as too like the ground"),
    ("a hue in turns, which rspamd does not read", '<div style="color:#FBFAF6"><p style="color:hsl(0.1667turn,6%,10%)">Ink in a browser.</p></div>', "rspamd reads its colour as too like the ground"),
    ("a colour attribute with a space before it, which rspamd does not read", '<div style="color:#FBFAF6"><font color=" #1A1A17">Ink in a browser.</font></div>', "rspamd reads its colour as too like the ground"),
    ("a colour attribute's name in capitals, which rspamd does not read", '<div style="color:#FBFAF6"><font color="BLACK">Ink in a browser.</font></div>', "rspamd reads its colour as too like the ground"),
    ("an opacity with a trailing dot, which rspamd reads and a browser drops", '<p style="opacity:0.">Faded words.</p>', "opacity:0., under 0.1, which rspamd reads"),
    ("a font size with a trailing dot, which rspamd reads and a browser drops", '<p style="font-size:2.px">Small words.</p>', "rspamd reads its font size as 2px"),
    ("an opacity rspamd reads after an important one, a trailing dot and all", '<p style="opacity:1 !important;opacity:0.05.">Faded words.</p>', "opacity:0.05., under 0.1, which rspamd reads"),
    ("an opacity rspamd reads off a unit it does not know, after an important one", '<p style="opacity:1 !important;opacity:0.05x">Faded words.</p>', "opacity:0.05x, under 0.1, which rspamd reads"),
    ("an opacity rspamd reads with an exponent, after an important one", '<p style="opacity:1 !important;opacity:5e-2">Faded words.</p>', "opacity:5e-2, under 0.1, which rspamd reads"),
    ("a font size rspamd reads as a unitless 2.5, after an important one", '<p style="font-size:16px !important;font-size:2.5.px">Small words.</p>', "rspamd reads its font size as 2px"),
    ("a unitless font size rspamd reads in px, over a later shorthand", '<p style="font-size:2;font:16px a">Small words.</p>', "rspamd reads its font size as 2px"),
    ("a font size rspamd reads with an exponent, over a later shorthand", '<p style="font-size:2e0px;font:16px a">Small words.</p>', "rspamd reads its font size as 2px"),
    ("a percentage rspamd reads with a trailing dot, after an important size", '<p style="font-size:16px !important;font-size:10.%">Small words.</p>', "rspamd reads its font size as 1px"),
    ("a second font shorthand's line height, which rspamd keeps as the size", '<p style="font:16px a;font:16px/2px b">Small words.</p>', "rspamd reads its font size as 2px"),
    ("a colour rspamd reads after an important one, its channels with trailing dots", '<p style="color:#1A1A17 !important;color:rgb(251.,250.,246.)">Ink words.</p>', "rspamd reads its colour as too like"),
    ("an hsl() colour rspamd reads after an important one, its hue with a trailing dot", '<p style="color:#1A1A17 !important;color:hsl(48.,38%,97%)">Ink words.</p>', "rspamd reads its colour as too like"),
    ("grey, which rspamd reads at X11's value, on a ground of that value", '<table><tr><td style="background-color:#BEBEBE"><p style="color:grey">Grey words.</p></td></tr></table>', "rspamd reads its colour as too like"),
    ("a background shorthand's last colour, which rspamd keeps, after an important one", '<table><tr><td style="background:#1A1A17 !important;background:#1A1A17 #FBFAF6"><p style="color:#FBFAF6">Pale words.</p></td></tr></table>', "rspamd reads its colour as too like"),
    ("an overflow rspamd reads off its last name, at a height of 0", '<div style="overflow:visible !important;overflow:hidden 0;height:0">Clipped words.</div>', "rspamd reads height as 0 under overflow:hidden"),
    ("a font size rspamd reads across a comment, after an important size", '<p style="font-size:16px !important;font-size:2/**/px">Small words.</p>', "rspamd reads its font size as 2px"),
    ("a hash rspamd reads with digits no hex holds, as black, after an important colour", '<table><tr><td style="background-color:#000000"><p style="color:#FBFAF6 !important;color:#zzzzzz">Pale words.</p></td></tr></table>', "rspamd reads its colour as too like"),
    ("a colour function rspamd reads a string in as 0, after an important colour", '<table><tr><td style="background-color:#001A17"><p style="color:#FBFAF6 !important;color:rgb(&quot;x&quot;,26,23)">Pale words.</p></td></tr></table>', "rspamd reads its colour as too like"),
    ("a colour rspamd reads off percentages of each channel, after an important ink", '<p style="color:#1A1A17 !important;color:rgb(98.5%,98%,96.5%)">Ink words.</p>', "rspamd reads its colour as too like"),
    ("an alpha rspamd reads off a percentage, after an important ink", '<p style="color:#1A1A17 !important;color:rgba(26,26,23,3%)">Ink words.</p>', "rspamd reads its colour as transparent"),
    ("a font size rspamd reads off a cut exponent, after an important size", '<p style="font-size:16px !important;font-size:2e+px">Small words.</p>', "rspamd reads its font size as 2px"),
    ("a display rspamd reads off its last name, after an important one", '<p style="display:block !important;display:inline none">Hidden words.</p>', "rspamd reads <p> as display:none"),
    ("a block in brackets, which ends rspamd's reading before a later opacity", '<p style="opacity:0.05;font-family:a [b];opacity:1">Faded words.</p>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("a second semicolon, after which rspamd skips a declaration", '<p style="opacity:0.05;;opacity:1">Faded words.</p>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("a property with no colon, after which rspamd skips a declaration", '<p style="opacity:0.05;color;opacity:1">Faded words.</p>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("a function where rspamd looks for a property's name, which it reads past", '<p style="rgb(1,2,3)opacity:0.05">Faded words.</p>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("an opacity rspamd reads where a function's first ) ends it, in a family a browser drops", '<p style="font-family:x((a);opacity:0.05;b)">Faded words.</p>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("a text indent rspamd reads off the page, out of a family a browser drops", '<p style="font-family:x((a);text-indent:-9999px;b)">Indented words.</p>', "which rspamd reads as off the page"),
    ("a clip rspamd reads as clipping to nothing, out of a family a browser drops", '<p style="font-family:x((a);clip:rect(0,0,0,0);b)">Clipped words.</p>', "which rspamd reads as off the page"),
    ("a position rspamd reads off the page, out of a family a browser drops", '<p style="font-family:x((a);position:absolute;left:-9999px;b)">Placed words.</p>', "which rspamd reads as off the page"),
    ("a hash rspamd reads as a colour function, after an important colour", '<table><tr><td style="background-color:#1A1A17"><p style="color:#FBFAF6 !important;color:#rgb(26,26,23)">Pale words.</p></td></tr></table>', "rspamd reads its colour as too like"),
    ("font-color, which rspamd reads as a colour and a browser does not know", '<p style="font-color:#FBFAF6">Pale words.</p>', "rspamd reads its colour as too like"),
    ("bgcolor as a property, which rspamd reads as a ground and a browser does not know", '<div style="bgcolor:#1A1A17"><p style="color:#1A1A17">Dark words.</p></div>', "rspamd reads its colour as too like"),
    ("a percentage height rspamd takes of a parent's 10 px and cuts to 0, under a clip a browser does not apply", '<div style="height:10px"><p style="overflow:visible !important;overflow:hidden;height:5%">Clipped words.</p></div>', "rspamd reads height as 0 under overflow:hidden"),
    ("a negative height rspamd reads as a percentage of a parent's 10 px, under a clip a browser does not apply", '<div style="height:10px"><p style="overflow:visible !important;overflow:hidden;height:-5px">Clipped words.</p></div>', "rspamd reads height as 0 under overflow:hidden"),
    ("rspamd's reading cut off at 1 << 17 tokens, before a later opacity", '<p style="opacity:0.05;' + "a;" * 40000 + 'opacity:1">Faded words.</p>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("an opacity rspamd keeps where brackets nest past 20 levels and stop its reading", '<p style="opacity:0.05 ' + "(" * 21 + '">Faded words.</p>', f"opacity:0.05 {'(' * 21}, under 0.1, which rspamd reads"),
    ("a comment left open, whose last byte rspamd reads", '<p style="opacity:1/*0">Faded words.</p>', "opacity:1/*0, under 0.1, which rspamd reads"),
    ("a string that holds a semicolon, to its own quote, which rspamd reads past", '<p style="opacity:0.05;font-family:&quot;a\';opacity:1&quot;">Faded words.</p>', "opacity:0.05, under 0.1, which rspamd reads"),
    ("a quote at a style's very end, which rspamd reads as a delimiter, not a string", '<p style="color:#1A1A17 !important;color:rgb(251,250,246&quot;">Ink words.</p>', "rspamd reads its colour as too like"),
    ("<!-- in a value, whose last - rspamd reads again, as a sign", '<p style="opacity:<!--0.5">Faded words.</p>', "opacity:<!--0.5, under 0.1, which rspamd reads"),
    ("a negative opacity rspamd reads as 0, after an important one", '<p style="opacity:1 !important;opacity:-1">Faded words.</p>', "opacity:-1, under 0.1, which rspamd reads"),
    ("an opacity with no digit before its dot, after an important one", '<p style="opacity:1 !important;opacity:.05">Faded words.</p>', "opacity:.05, under 0.1, which rspamd reads"),
    ("a number past a float's range, which rspamd reads as a delimiter, after an opacity", '<p style="opacity:1 !important;opacity:0.05 1e400">Faded words.</p>', "opacity:0.05 1e400, under 0.1, which rspamd reads"),
    ("a display's name rspamd reads again after a number, as a unit it does not know", '<p style="visibility:0hidden">Hidden words.</p>', "rspamd reads <p> as visibility:hidden"),
    ("an at-keyword rspamd reads as a colour function, after an important colour", '<table><tr><td style="background-color:#1A1A17"><p style="color:#FBFAF6 !important;color:@rgb(26,26,23)">Pale words.</p></td></tr></table>', "rspamd reads its colour as too like"),
    ("an overflow rspamd reads before !important, out of a family a browser drops", '<div style="height:0"><p style="font-family:x((a);overflow:hidden !important;b)">Clipped words.</p></div>', "rspamd reads height as 0 under overflow:hidden"),
    ("a font shorthand's colour rspamd joins to the size an earlier one set", '<p style="font:16px a;font:white">Pale words.</p>', "rspamd reads its colour as too like"),
    ("font-color, which rspamd applies after an earlier color", '<p style="color:#1A1A17;font-color:#FBFAF6">Pale words.</p>', "rspamd reads its colour as too like"),
    ("background-color, which rspamd reads over a later background shorthand", '<table><tr><td style="background-color:#1A1A17;background:#FBFAF6"><p style="color:#1A1A17">Dark words.</p></td></tr></table>', "rspamd reads its colour as too like"),
    ("a fixed box rspamd reads off the page by its top, out of a family a browser drops", '<p style="font-family:x((a);position:fixed;top:-9999px;b)">Placed words.</p>', "which rspamd reads as off the page"),
    ("a text indent of -1000 px, which rspamd reads off the page, out of a family a browser drops", '<p style="font-family:x((a);text-indent:-1000px;b)">Indented words.</p>', "which rspamd reads as off the page"),
    ("an inset() of 50%, which rspamd reads as clipping to nothing, out of a family a browser drops", '<p style="font-family:x((a);clip-path:inset(50%);b)">Clipped words.</p>', "which rspamd reads as off the page"),
    ("a circle() of 0, which rspamd reads as clipping to nothing, out of a family a browser drops", '<p style="font-family:x((a);clip-path:circle(0);b)">Clipped words.</p>', "which rspamd reads as off the page"),
    ("a percentage height rspamd takes of the 8 px it reads 1% of 800 px as, under a clip a browser does not apply", '<div style="height:1%"><p style="overflow:visible !important;overflow:hidden;height:10%">Clipped words.</p></div>', "rspamd reads height as 0 under overflow:hidden"),
    ("a percentage under 1%, which rspamd stores in 16 bits as 0 px, under a clip a browser does not apply", '<p style="overflow:visible !important;overflow:hidden;width:0.5%">Clipped words.</p>', "rspamd reads width as 0 under overflow:hidden"),
    ("a clip rspamd rounds to 1 px as a C float, which clips to nothing, out of a family a browser drops", '<p style="font-family:x((a);clip:rect(0,0,1.00000001px,0);b)">Clipped words.</p>', "which rspamd reads as off the page"),
    ("a hue rspamd cuts past a C int's range, to 232 degrees, on a ground of that hue, after an important colour", '<table><tr><td style="background-color:#0022FF"><p style="color:#FBFAF6 !important;color:hsl(2147483648,100%,50%)">Pale words.</p></td></tr></table>', "rspamd reads its colour as too like"),
    ("a name with a byte past ASCII after a colour, which rspamd does not read as black, after an important ink", '<p style="color:#1A1A17 !important;color:#FBFAF6 blac\u212a">Ink words.</p>', "rspamd reads its colour as too like"),
    ("a font shorthand's last colour, which rspamd keeps", '<p style="font:16px #1A1A17 white">Pale words.</p>', "rspamd reads its colour as too like"),
    ("black with a byte past ASCII after it, which rspamd reads as one name and no colour, after an important ink", '<p style="color:#1A1A17 !important;color:#FBFAF6 black\u00e9">Ink words.</p>', "rspamd reads its colour as too like"),
    ("a background shorthand's last colour, which rspamd takes as the ground, out of a family a browser drops", '<p style="color:#1A1A17;font-family:x((a);background:#FBFAF6 #1A1A17;b)">Ink words.</p>', "rspamd reads its colour as too like"),
    ("a height a max-height of 0 px caps in its own unit, which rspamd reads as 0 under a clip, out of a family a browser drops", '<p style="font-family:x((a);overflow:hidden;height:10px;max-height:0px;b)">Clipped words.</p>', "rspamd reads height as 0 under overflow:hidden"),
    ("a vertical tab, which rspamd reads as no space, so it skips the size after it, out of a family a browser drops", '<p style="font-family:x((a);font-size:1px;b); \x0bfont-size:16px">Small words.</p>', "rspamd reads its font size as 1px"),
    # Broken: read stricter than a browser, which shows the text (the reader's documented strictness).
    ("a span's size and overflow, which a browser ignores, read stricter than a browser", '<span style="height:2px;overflow:hidden">Inline words.</span>', "height:2px under overflow-y:hidden"),
    ("a cell's height attribute under a clip, which its row grows past, read stricter than a browser", '<table><tr><td height="1" style="overflow:hidden">Cell words.</td></tr></table>', 'height="1" under overflow-y:hidden'),
    ("a table's height under a clip, which it grows past, read stricter than a browser", '<div style="display:table;height:2px;overflow:hidden">Table words.</div>', "height:2px under overflow-y:hidden"),
    ("a box under a collapsed block set visible again, which a browser shows, read stricter than a browser", '<div style="visibility:collapse;display:block"><p style="visibility:visible">Shown again.</p></div>', "visibility:collapse, which hides all it holds whatever a box below sets"),
    # Refused: hiding the reader does not model or resolve, a property or an element it does not read, and a box that clips
    # text at any size it cannot tell is under 4 px, though a browser may show the text there (fail closed).
    ("a box moved off the page", '<p style="position:absolute;left:-9999px">Off the page.</p>', "sets position:absolute"),
    ("a line indented out of its box", '<p style="text-indent:-9999px">Indented away.</p>', "sets text-indent:-9999px"),
    ("a box scaled to nothing", '<p style="transform:scale(0)">Scaled away.</p>', "sets transform:scale(0)"),
    ("a box clipped by clip", '<p style="clip:rect(0 0 0 0)">Clipped away.</p>', "sets clip:rect(0 0 0 0)"),
    ("a box clipped by clip-path", '<p style="clip-path:inset(50%)">Clipped away.</p>', "sets clip-path:inset(50%)"),
    ("scale:0", '<p style="scale:0">Scaled away.</p>', "sets scale:0"),
    ("translate off the page", '<p style="translate:-9999px">Moved away.</p>', "sets translate:-9999px"),
    ("zoom to a hundredth", '<p style="zoom:0.01">Shrunk away.</p>', "sets zoom:0.01"),
    ("filter:opacity(0)", '<p style="filter:opacity(0)">Filtered away.</p>', "sets filter:opacity(0)"),
    ("a transparent mask", '<p style="mask-image:linear-gradient(transparent,transparent)">Masked away.</p>', "sets mask-image"),
    ("contain:strict", '<p style="contain:strict">Contained away.</p>', "sets contain:strict"),
    ("a line clamp", '<p style="-webkit-line-clamp:1">Clamped lines.</p>', "sets -webkit-line-clamp:1"),
    ("a transparent text fill", '<p style="-webkit-text-fill-color:transparent">Unfilled words.</p>', "sets -webkit-text-fill-color:transparent"),
    ("a negative margin off the page", '<p style="margin-left:-9999px">Moved away.</p>', "sets margin-left:-9999px"),
    ("a gradient ground", '<div style="background:linear-gradient(#FBFAF6,#FBFAF6)"><p style="color:#FBFAF6">White on a gradient.</p></div>', "sets background:linear-gradient"),
    ("an image ground", '<div style="background-image:url(https://e.test/g.png)"><p>Words on an image.</p></div>', "sets background-image:url"),
    ("a font size from calc()", '<p style="font-size:calc(0px)">Computed size.</p>', "sets font-size:calc(0px)"),
    ("a font size from a custom property", '<p style="--z:0px;font-size:var(--z)">Computed size.</p>', "sets font-size:var(--z)"),
    ("a font size with an exponent", '<p style="font-size:1e-9px">Computed size.</p>', "sets font-size:1e-9px"),
    ("a font size in a viewport unit", '<p style="font-size:0.1vw">Computed size.</p>', "sets font-size:0.1vw"),
    ("a system font in the shorthand", '<p style="font:caption">System words.</p>', "sets font:caption"),
    ("an opacity from calc()", '<p style="opacity:calc(0)">Computed opacity.</p>', "sets opacity:calc(0)"),
    ("visibility from a custom property", '<p style="visibility:var(--v)">Computed visibility.</p>', "sets visibility:var(--v)"),
    ("a colour from a custom property", '<p style="color:var(--c)">Computed colour.</p>', "sets color:var(--c)"),
    ("a colour from light-dark()", '<p style="color:light-dark(#FBFAF6,#FBFAF6)">Computed colour.</p>', "sets color:light-dark"),
    ("a clip at a height from calc()", '<p style="max-height:calc(0px);overflow:hidden">Computed clip.</p>', "<p> sets overflow:hidden"),
    ("a clip at a percentage height", '<p style="height:0%;overflow:hidden">Computed clip.</p>', "<p> sets overflow:hidden"),
    ("a clip at a line height of 0", '<p style="line-height:0;overflow:hidden">Clipped lines.</p>', "<p> sets overflow:hidden"),
    ("a clip at a height that cuts its line", '<p style="line-height:24px;height:4px;overflow:hidden">Clipped words.</p>', "<p> sets overflow:hidden"),
    ("a clip at a height its large text overflows", '<p style="font-size:100px;height:5px;overflow:hidden">Clipped words.</p>', "<p> sets overflow:hidden"),
    ("a box that clips at 4 px", '<p style="max-height:4px;overflow:hidden">A thin box.</p>', "<p> sets overflow:hidden"),
    ("a box that clips at a size that shows its line", '<p style="max-height:600px;overflow:hidden">A tall box.</p>', "<p> sets overflow:hidden"),
    ("a clip on lines that keep from wrapping, in a box of a set width", '<div style="width:200px"><p style="white-space:nowrap;overflow:hidden">A line that never wraps and runs on past its box.</p></div>', "<p> sets overflow:hidden"),
    ("a <pre> that clips its lines, which a browser's own sheet keeps from wrapping", '<div style="width:200px"><pre style="overflow:hidden">A preformatted line that runs on past its box.</pre></div>', "<pre> sets overflow:hidden"),
    ("a clip at a percentage width attribute", '<table><tr><td width="50%" style="overflow:hidden">Cell words.</td></tr></table>', "<td> sets overflow:hidden"),
    ("a cell's width attribute under a width its style sets, which overrides it", '<table><tr><td width="1" style="width:300px;overflow:hidden">Cell words.</td></tr></table>', "<td> sets overflow:hidden"),
    ("a min height in percent the reader does not resolve, over a clip of no height", '<p style="height:0;min-height:50%;overflow:hidden">Words.</p>', "<p> sets overflow:hidden"),
    ("a min height inherited over a clip of no height", '<div style="min-height:40px"><p style="height:0;min-height:inherit;overflow:hidden">Words.</p></div>', "<p> sets overflow:hidden"),
    ("an overflow the reader does not read", '<p style="height:0;overflow:inherit">Words.</p>', "sets overflow:inherit"),
    ("a clip margin that widens a clip", '<p style="overflow:clip;overflow-clip-margin:20px">Words.</p>', "sets overflow-clip-margin:20px"),
    ("a font shorthand with a custom property", '<div style="font-size:0"><p style="font:16px var(--f)">Words.</p></div>', "sets font:16px var(--f)"),
    ("content-visibility from a custom property", '<p style="--v:hidden;content-visibility:var(--v)">Words.</p>', "sets content-visibility:var(--v)"),
    ("a content-visibility the reader does not read", '<p style="content-visibility:inherit">Words.</p>', "sets content-visibility:inherit"),
    ("a margin from calc()", '<p style="margin-top:calc(0px - 9999px)">Words.</p>', "sets margin-top:calc(0px - 9999px)"),
    ("a display from a custom property", '<p style="--d:none;display:var(--d)">Words.</p>', "sets display:var(--d)"),
    ("an outline that paints over the text before it", '<p>Covered words.</p><span style="display:inline-block;outline:600px solid #FBFAF6"></span>', "sets outline:600px solid #fbfaf6"),
    ("a shadow that paints over the text before it", '<p>Covered words.</p><span style="display:inline-block;box-shadow:0 0 0 600px #FBFAF6"></span>', "sets box-shadow:0 0 0 600px #fbfaf6"),
    ("letter spacing that stacks the letters", '<p style="letter-spacing:-1000px">Stacked letters.</p>', "sets letter-spacing:-1000px"),
    ("word spacing that stacks the words", '<p style="word-spacing:-9999px">Stacked words here.</p>', "sets word-spacing:-9999px"),
    ("a spacing from calc()", '<p style="letter-spacing:calc(1px - 1000px)">Stacked letters.</p>', "sets letter-spacing:calc(1px - 1000px)"),
    ("a colour tinycss2 does not convert", '<p style="color:lab(10% 0 0)">Lab words.</p>', "sets color:lab(10% 0 0)"),
    ("a closed details", "<details><summary>Shown.</summary>Folded words.</details>", "a closed <details>"),
    ("a closed details' second summary", "<details><summary>Shown.</summary><summary>Second summary words.</summary></details>", "a closed <details>, outside its first summary"),
    ("a closed select's options", "<select><option>First</option><option>Second option words.</option></select>", "<option> holds text in <select>"),
    ("a text area's text", '<textarea style="height:0">Area words.</textarea>', "<textarea> holds text in <textarea>"),
    ("an SVG's text", '<svg width="80" height="20"><text x="0" y="15">SVG words</text></svg>', "<text> holds text in <svg>"),
    ("an SVG's description", '<svg width="10" height="10"><desc>Described words.</desc></svg>', "<desc> holds text in <svg>"),
    ("a video's fallback", "<video>Fallback words.</video>", "<video> holds text in <video>"),
    ("an audio's fallback", "<audio controls>Fallback words.</audio>", "<audio> holds text in <audio>"),
    ("an iframe's fallback", "<iframe>Fallback words.</iframe>", "<iframe> holds text in <iframe>"),
    ("a block that clips in a container of no width", '<div style="max-width:0"><p style="overflow:hidden">Clipped words.</p></div>', "<p> sets overflow:hidden"),
    ("a block that clips in a container 2 px wide", '<div style="width:2px"><p style="overflow:hidden">Clipped words.</p></div>', "<p> sets overflow:hidden"),
    ("a block that clips in a container 0% wide", '<div style="width:0%"><p style="overflow:hidden">Clipped words.</p></div>', "<p> sets overflow:hidden"),
    ("a span set to display:block that clips in a container 2 px wide", '<div style="width:2px"><span style="display:block;overflow:hidden">Clipped words.</span></div>', "<span> sets overflow:hidden"),
    ("a box that clips with no size, which grows to its lines", '<p style="overflow:hidden">Words in a box that grows.</p>', "<p> sets overflow:hidden"),
    ("a clip on one axis beside a visible one, which leaves it visible", '<p style="overflow:clip visible;height:0">Words.</p>', "<p> sets overflow:clip visible"),
    ("a block that clips in a container that shows its words", '<div style="width:300px"><p style="overflow:hidden">Words in a wide box.</p></div>', "<p> sets overflow:hidden"),
    ("an inline block that clips in a narrow container, as wide as its words", '<div style="width:2px"><span style="display:inline-block;overflow:hidden">Words.</span></div>', "<span> sets overflow:hidden"),
    ("a height a span sets over the one rspamd hands down", '<span style="height:0"><span style="height:20px;overflow:hidden">Words.</span></span>', "<span> sets overflow:hidden"),
    ("a line that keeps from wrapping in a cell, which grows with it", '<p style="white-space:nowrap;overflow:hidden">A line that never wraps.</p>', "<p> sets overflow:hidden"),
    ("a block that clips in a cell, which grows past a narrow container", '<div style="width:2px"><table><tr><td><p style="overflow:hidden">Words in a cell.</p></td></tr></table></div>', "<p> sets overflow:hidden"),
    ("a vendor's transform, a property the reader does not read", '<p style="-webkit-transform:scale(0)">Scaled away.</p>', "sets -webkit-transform:scale(0), a property this reader does not read"),
    ("a vendor's filter", '<p style="-webkit-filter:opacity(0)">Filtered away.</p>', "sets -webkit-filter:opacity(0)"),
    ("a vendor's clip path", '<p style="-webkit-clip-path:inset(50%)">Clipped away.</p>', "sets -webkit-clip-path:inset(50%)"),
    ("a vendor's shadow that paints over the text before it", '<p>Covered words.</p><span style="display:inline-block;-webkit-box-shadow:0 0 0 600px #FBFAF6"></span>', "sets -webkit-box-shadow:0 0 0 600px #fbfaf6"),
    ("a vendor's mask image", '<p style="-webkit-mask-box-image:linear-gradient(transparent,transparent)">Masked away.</p>', "sets -webkit-mask-box-image"),
    ("a mask border", '<p style="mask-border:linear-gradient(transparent,transparent)">Masked away.</p>', "sets mask-border"),
    ("a font size adjusted to nothing", '<p style="font-size-adjust:0">Adjusted away.</p>', "sets font-size-adjust:0"),
    ("a stroke in the ground's colour over the letters", '<p style="-webkit-text-stroke:6px #FBFAF6">Stroked away.</p>', "sets -webkit-text-stroke:6px #fbfaf6"),
    ("letters drawn as discs", '<p style="-webkit-text-security:disc">Secret words.</p>', "sets -webkit-text-security:disc"),
    ("an element's content replaced by an image", '<p style="content:url(https://e.test/a.png)">Replaced words.</p>', "sets content:url(https://e.test/a.png)"),
    ("a ground clipped to the text", '<div style="background:#1A1A17"><p style="background-color:#FBFAF6;background-clip:text;color:#1A1A17">Clipped ground words.</p></div>', "sets background-clip:text"),
    ("a background shorthand that clips its ground to the text, which Chromium takes", '<div style="background:#1A1A17"><p style="background:#FBFAF6 text;color:#1A1A17">Shorthand text words.</p></div>', "sets background:#fbfaf6 text"),
    ("a box moved along a ray", '<p style="offset-path:ray(180deg);offset-distance:9999px">Moved words.</p>', "sets offset-path:ray(180deg)"),
    ("a logical overflow that clips at no height", '<p style="overflow-block:hidden;height:0">Clipped words.</p>', "sets overflow-block:hidden"),
    ("all:initial, which sets the colour back to black", '<div style="background:#1A1A17;color:#FBFAF6"><p style="all:initial">Black on ink.</p></div>', "sets all:initial"),
    ("a column laid out from its end, above its box", '<div style="display:flex;flex-direction:column-reverse;height:0"><p>Reversed words.</p></div>', "sets flex-direction:column-reverse"),
    ("an Outlook property the reader does not read", '<p style="mso-line-height-rule:exactly;line-height:1px">Outlook lines.</p>', "sets mso-line-height-rule:exactly"),
    ("a text shadow", '<p style="color:transparent;text-shadow:0 0 0 #1A1A17">Shadow words.</p>', "sets text-shadow:0 0 0 #1a1a17"),
    ("a decoration's thickness over the letters", '<p style="text-decoration:line-through;text-decoration-color:#FBFAF6;text-decoration-thickness:1em">Banded words.</p>', "sets text-decoration-thickness:1em"),
    ("a decoration's thickness in the shorthand", '<p style="text-decoration:line-through #FBFAF6 1em">Banded words.</p>', "sets text-decoration:line-through #fbfaf6 1em"),
    ("an underline moved over the letters", '<p style="text-decoration:underline;text-underline-offset:-0.5em">Underlined words.</p>', "sets text-underline-offset:-0.5em"),
    ("a dark colour scheme in the style", '<p style="color-scheme:light dark">Words.</p>', "sets color-scheme:light dark"),
    ("a dark colour scheme in a meta, which Chromium reads in the body too", '<meta name="color-scheme" content="light dark"><p>Words.</p>', "<meta> sets color-scheme:light dark"),
    ("Apple's older colour scheme meta asking for dark", '<meta name="supported-color-schemes" content="light dark"><p>Words.</p>', "<meta> sets supported-color-schemes:light dark"),
    ("a cell's background image", '<table><tr><td background="https://e.test/g.png">Words on an image.</td></tr></table>', "<td> sets the background attribute"),
    ("a column's ground behind its cells", '<table><colgroup><col style="background-color:#1A1A17"></colgroup><tr><td style="color:#1A1A17">Dark on a dark column.</td></tr></table>', "<col> sets background-color:#1a1a17, which a column paints"),
    ("a column group's ground behind its cells", '<table><colgroup style="background:#1A1A17"><col></colgroup><tr><td style="color:#1A1A17">Dark on a dark group.</td></tr></table>', "<colgroup> sets background:#1a1a17"),
    ("a column's bgcolor, which a browser paints behind its cells", '<table><colgroup><col bgcolor="#1A1A17"></colgroup><tr><td style="color:#1A1A17">Dark on a col bgcolor.</td></tr></table>', "<col> sets bgcolor"),
    ("a collapsed column", '<table><colgroup><col style="visibility:collapse"><col></colgroup><tr><td>Collapsed column words.</td><td>B</td></tr></table>', "<col> sets visibility:collapse"),
    ("an open dialog, which a browser places over the page", "<p>Words a dialog covers.</p><dialog open></dialog>", "<dialog> sits over the page"),
    ("a popover a page gives a display, over the page", '<p>Words a popover covers.</p><div popover style="display:block;width:600px;height:400px"></div>', "<div> sits over the page"),
    ("a declarative shadow root, shown in place of its parent's content", '<div><template shadowrootmode="open"><p>Shadow words.</p></template>Light words.</div>', "<template> sets shadowrootmode"),
    ("a meter's fallback", '<meter value="0.5">Meter words.</meter>', "<meter> holds text in <meter>"),
    ("a progress bar's fallback", '<progress value="0.5">Progress words.</progress>', "<progress> holds text in <progress>"),
    ("a marquee's text, scrolled through its box", "<marquee>Marquee words.</marquee>", "<marquee> holds text in <marquee>"),
    ("a noscript's text, which a browser that runs scripts never shows", "<noscript>Noscript words.</noscript>", "holds text in <noscript>"),
    ("a formula's annotation, which a browser never shows", "<math><semantics><mi>x</mi><annotation>Annotation words.</annotation></semantics></math>", "<annotation> holds text in <math>"),
    ("a fencedframe's text, which a browser never shows", "<fencedframe>Fenced words.</fencedframe>", "<fencedframe> holds text in <fencedframe>"),
    ("an element the reader does not know", "<x-note>Custom words.</x-note>", "<x-note> holds text in <x-note>"),
    ("a font shorthand with no family, which a browser drops", '<div style="font-size:0"><p style="font:16px">Words.</p></div>', "sets font:16px,"),
    ("a font shorthand cut after its slash, which a browser drops", '<div style="font-size:0"><p style="font:16px/">Words.</p></div>', "sets font:16px/,"),
    ("a font shorthand with a number for a family, which a browser drops", '<div style="font-size:0"><p style="font:16px 0 a">Words.</p></div>', "sets font:16px 0 a,"),
    ("a font shorthand whose family mixes a string and a name, which a browser drops", '<div style="font-size:0"><p style="font:16px &#39;a&#39; b">Words.</p></div>', 'sets font:16px "a" b,'),
    ("a font shorthand ending in a comma, which a browser drops", '<div style="font-size:0"><p style="font:16px a,">Words.</p></div>', "sets font:16px a,,"),
    ("a font shorthand with an empty family between commas, which a browser drops", '<div style="font-size:0"><p style="font:16px a,,b">Words.</p></div>', "sets font:16px a,,b,"),
    ("a font shorthand whose family is a CSS-wide keyword, which a browser drops", '<div style="font-size:0"><p style="font:16px inherit">Words.</p></div>', "sets font:16px inherit,"),
    ("a font shorthand whose family is default, which a browser drops", '<div style="font-size:0"><p style="font:16px default">Words.</p></div>', "sets font:16px default,"),
    ("a font shorthand with a name after a generic family, which a browser drops", '<div style="font-size:0"><p style="font:16px serif a">Words.</p></div>', "sets font:16px serif a,"),
    ("a font shorthand with a word before its size that it does not take, which a browser drops", '<div style="font-size:0"><p style="font:foo 16px a">Words.</p></div>', "sets font:foo 16px a,"),
    ("a font shorthand that sets its weight twice, which a browser drops", '<div style="font-size:0"><p style="font:bold bold 16px a">Words.</p></div>', "sets font:bold bold 16px a,"),
    ("a font shorthand with five words before its size, which a browser drops", '<div style="font-size:0"><p style="font:normal normal normal normal normal 16px a">Words.</p></div>', "sets font:normal normal normal normal normal 16px a,"),
    ("a font shorthand with a weight past 1000, which a browser drops", '<div style="font-size:0"><p style="font:1001 16px a">Words.</p></div>', "sets font:1001 16px a,"),
    ("a font shorthand with no size, which a browser drops", '<div style="font-size:0"><p style="font:bold">Words.</p></div>', "sets font:bold,"),
    ("a font shorthand whose size is a CSS-wide keyword, which a browser drops, after a size of 0", '<p style="font-size:0;font:bold inherit a">Words.</p>', "sets font:bold inherit a,"),
    ("a font shorthand with a line height that is no length, which a browser drops", '<div style="font-size:0"><p style="font:16px/a a">Words.</p></div>', "sets font:16px/a a,"),
    ("a font shorthand with a negative line height, which a browser drops", '<div style="font-size:0"><p style="font:16px/-1 a">Words.</p></div>', "sets font:16px/-1 a,"),
    ("a font shorthand with a line height in a unit a browser does not know", '<div style="font-size:0"><p style="font:16px/2foo a">Words.</p></div>', "sets font:16px/2foo a,"),
    ("a negative font size, which a browser drops", '<div style="font-size:0"><p style="font-size:-16px">Words.</p></div>', "sets font-size:-16px"),
    ("a decoration's thickness from calc() in the shorthand", '<p style="text-decoration:line-through #FBFAF6 calc(1em)">Banded words.</p>', "sets text-decoration:line-through #fbfaf6 calc(1em)"),
    ("a decoration's thickness from max() in the shorthand", '<p style="text-decoration:line-through #FBFAF6 max(1em, 1px)">Banded words.</p>', "sets text-decoration:line-through #fbfaf6 max(1em, 1px)"),
    ("a decoration's thickness with an exponent in the shorthand", '<p style="text-decoration:line-through #FBFAF6 1e1px">Banded words.</p>', "sets text-decoration:line-through #fbfaf6 1e1px"),
    ("content-visibility:auto, which clips its box as overflow:clip does", '<div style="content-visibility:auto;height:0">Contained words.</div>', "sets content-visibility:auto"),
    ("content-visibility:auto on a box that grows to its text, which a browser shows", '<p style="content-visibility:auto">Contained words.</p>', "sets content-visibility:auto"),
    ("a box laid out as a table's column, collapsed, which collapses its cells", '<div style="display:table"><div style="display:table-column;visibility:collapse"></div><div style="display:table-row"><div style="display:table-cell">Collapsed cell words.</div></div></div>', "<div> sets visibility:collapse, which a column"),
    ("a box laid out as a column group in an inline table, collapsed", '<div style="display:inline-table"><div style="display:table-column-group;visibility:collapse"></div><div style="display:table-row"><div style="display:table-cell">Collapsed cell words.</div></div></div>', "<div> sets visibility:collapse, which a column"),
    ("a column in a column group laid out as one, collapsed", '<table><colgroup style="display:table-column-group"><col style="visibility:collapse"></colgroup><tr><td>Collapsed column words.</td></tr></table>', "<col> sets visibility:collapse, which a column"),
    ("a column's ground in a column group laid out as one", '<table><colgroup style="display:table-column-group"><col style="background-color:#1A1A17"></colgroup><tr><td style="color:#1A1A17">Dark on a dark column.</td></tr></table>', "<col> sets background-color:#1a1a17, which a column"),
    ("a box laid out as a column in a box laid out as a column group, collapsed", '<div style="display:table"><div style="display:table-column-group"><div style="display:table-column;visibility:collapse"></div></div><div style="display:table-row"><div style="display:table-cell">Collapsed column words.</div></div></div>', "<div> sets visibility:collapse, which a column"),
    ("a ground on a box laid out as a column in a box laid out as a column group", '<div style="display:table"><div style="display:table-column-group"><div style="display:table-column;background-color:#1A1A17"></div></div><div style="display:table-row"><div style="display:table-cell;color:#1A1A17">Dark on a dark column.</div></div></div>', "<div> sets background-color:#1a1a17, which a column"),
    ("a font size in ex, which the face's letters set", '<p style="font-size:0.5ex">Small words.</p>', "sets font-size:0.5ex"),
    ("a font size in ch, which the face's letters set", '<p style="font-size:0.5ch">Small words.</p>', "sets font-size:0.5ch"),
    ("a font size of 0 in a unit that is no length's, which a browser drops", '<p style="font-size:0deg">Words.</p>', "sets font-size:0deg"),
    ("a font shorthand sized 0 in a unit that is no length's, which a browser drops", '<p style="font:0deg a">Words.</p>', "sets font:0deg a,"),
    ("a column in a column group set content-visibility:hidden, collapsed", '<table><colgroup style="content-visibility:hidden"><col style="visibility:collapse"></colgroup><tr><td>Collapsed column words.</td></tr></table>', "<col> sets visibility:collapse, which a column"),
    ("a column in a column group hidden until found, collapsed", '<table><colgroup hidden="until-found"><col style="visibility:collapse"></colgroup><tr><td>Collapsed column words.</td></tr></table>', "<col> sets visibility:collapse, which a column"),
    ("a column in a column group at an opacity of 0.05, collapsed", '<table><colgroup style="opacity:0.05"><col style="visibility:collapse"></colgroup><tr><td>Collapsed column words.</td></tr></table>', "<col> sets visibility:collapse, which a column"),
    ("a column's ground in a column group set content-visibility:hidden", '<table><colgroup style="content-visibility:hidden"><col style="background-color:#1A1A17"></colgroup><tr><td style="color:#1A1A17">Dark on a dark column.</td></tr></table>', "<col> sets background-color:#1a1a17, which a column"),
    ("a column's ground in a column group at an opacity of 0.05", '<table><colgroup style="opacity:0.05"><col style="background-color:#1A1A17"></colgroup><tr><td style="color:#1A1A17">Dark on a dark column.</td></tr></table>', "<col> sets background-color:#1a1a17, which a column"),
    ("a font size CSS does not write, 16.px, which a browser drops after a size of 0", '<p style="font-size:0;font-size:16.px">Words.</p>', "sets font-size:16.px"),
    ("a font size CSS does not write, under a parent at 0", '<div style="font-size:0"><p style="font-size:16.px">Words.</p></div>', "sets font-size:16.px"),
    ("an opacity CSS does not write, 1., which a browser drops after an opacity of 0", '<p style="opacity:0;opacity:1.">Words.</p>', "sets opacity:1."),
    ("a percentage size CSS does not write, 800.%, under a parent at 2 px", '<div style="font-size:2px"><p style="font-size:800.%">Words.</p></div>', "sets font-size:800.%"),
    ("a column's image in a column group set content-visibility:hidden", '<table><colgroup style="content-visibility:hidden"><col style="background-image:linear-gradient(#1A1A17,#1A1A17)"></colgroup><tr><td style="color:#1A1A17">Dark on a dark column.</td></tr></table>', "<col> sets background-image:linear-gradient"),
    ("a column's image in a column group at an opacity of 0.05", '<table><colgroup style="opacity:0.05"><col style="background-image:linear-gradient(#1A1A17,#1A1A17)"></colgroup><tr><td style="color:#1A1A17">Dark on a dark column.</td></tr></table>', "<col> sets background-image:linear-gradient"),
    ("a column's background attribute in a column group hidden until found", '<table><colgroup hidden="until-found"><col background="data:image/gif;base64,R0lGODlhAQABAIAAABoaFwAAACwAAAAAAQABAAACAkQBADs="></colgroup><tr><td style="color:#1A1A17">Dark on a dark column.</td></tr></table>', "<col> sets the background attribute"),
    ("a box laid out as a column, a later display a browser drops aside, collapsed", '<div style="display:table"><div style="display:table-column;display:bogus;visibility:collapse"></div><div style="display:table-row"><div style="display:table-cell">Collapsed words.</div></div></div>', "sets visibility:collapse, which a column"),
    ("a font size in Arabic-Indic digits after a size of 0, which a browser drops", '<p style="font-size:0;font-size:١٦px">Words.</p>', "sets font-size:١٦px"),
    ("an opacity in Arabic-Indic digits after an opacity of 0, which a browser drops", '<p style="opacity:0;opacity:١">Words.</p>', "sets opacity:١"),
    ("a colour only X11 knows after an important one, which rspamd reads", '<p style="color:#1A1A17 !important;color:navyblue">Ink words.</p>', "sets color:navyblue"),
    ("a colour attribute rspamd reads off a name only X11 knows", '<p><font color="gray50">Grey words.</font></p>', 'sets color="gray50"'),
    ("a font shorthand's family rspamd reads as a colour only X11 knows", '<p style="font:16px navyblue">Navy words.</p>', "sets font:16px navyblue"),
    ("a colour off one of X11's numbered names, after an important ink", '<p style="color:#1A1A17 !important;color:red3">Ink words.</p>', "sets color:red3"),
    ("a colour off X11's numbered lightgoldenrod, after an important ink", '<p style="color:#1A1A17 !important;color:lightgoldenrod2">Ink words.</p>', "sets color:lightgoldenrod2"),
    ("a font size past a float's range, which rspamd reads as no number", '<p style="font-size:1e400px">Sized words.</p>', "sets font-size:1e400px"),
    ("a style that holds an escape, which rspamd unescapes on terms of its own", '<p style="color:#1A1A1\\37">Ink words.</p>', "sets a style that holds a backslash or U+FFFD"),
    ("a NUL in a style, which the page's parser writes as U+FFFD", '<p style="color:#1A1A17;font-family:a&#0;b">Ink words.</p>', "sets a style that holds a backslash or U+FFFD"),
    ("a percentage height rspamd takes past 16 bits, which C++ leaves undefined", '<div style="height:32767px"><p style="overflow:visible !important;overflow:hidden;height:200%">Clipped words.</p></div>', "sets height:200%"),
    ("a style written with a character reference not closed with ;, which rspamd's HTML parser decodes on terms of its own", '<p title="a>b" style="font-family:&quot;Inter&quot;;color:#1A1A17&ampx">Ink words.</p>', "is written with a character reference"),
    ("a style written with a name HTML does not define, which rspamd's HTML parser decodes on terms of its own", '<p style="font-family:a&foo;b">Words.</p>', "is written with a character reference"),
    ("a style written with a reference to a code point HTML maps, a Windows dash", '<p style="font-family:a&#150;b">Words.</p>', "is written with a character reference"),
    ("a style written with a hex reference to a code point HTML maps", '<p style="font-family:a&#x85;b">Words.</p>', "is written with a character reference"),
    ("a style written with a reference to a surrogate, which HTML replaces", '<p style="font-family:a&#xD800;b">Words.</p>', "is written with a character reference"),
    ("a style written with a reference to NUL, which HTML replaces", '<p style="font-family:a&#0;b">Words.</p>', "is written with a character reference"),
    ("an unquoted style written with a character reference not closed with ;", "<p style=color:#1A1A17&ampx>Ink words.</p>", "is written with a character reference"),
    ("an unquoted style whose reference sits past a no-break space, which ends no value, and rspamd decodes into a string that swallows the size after it", "<p style=font-size:1px;font-family:x\u00a0&quotx;font-size:16px>Secret words here.</p>", "is written with a character reference"),
    ("an unquoted style whose reference sits past a vertical tab, which ends no value, and rspamd decodes into a string that swallows the size after it", "<p style=font-size:1px;font-family:x\x0b&quotx;font-size:16px>Secret words here.</p>", "is written with a character reference"),
    ("a single-quoted style written with a character reference not closed with ;", "<p style='color:#1A1A17&ampx'>Ink words.</p>", "is written with a character reference"),
    ("a colour attribute written with a character reference not closed with ;, which rspamd reads", '<p><font color="#1A1A17&ampx">Ink words.</font></p>', "a color attribute is written with a character reference"),
    ("a ground attribute written with a character reference not closed with ;, which rspamd reads", '<table><tr><td bgcolor="#FBFAF6&ampx">Words.</td></tr></table>', "a bgcolor attribute is written with a character reference"),
    ("a style after a colour attribute whose reference both parsers decode alike, written with one rspamd decodes into a string that swallows the size after it", '<p><font color="&#35;1A1A17" style=font-size:1px;font-family:x&quotx;font-size:16px>Secret words here.</font></p>', "a style attribute is written with a character reference"),
    ("a style after a ground attribute whose reference both parsers decode alike, written with one rspamd decodes into a string that swallows the size after it", '<table><tr><td bgcolor="&#35;FBFAF6" style=font-size:1px;font-family:x&quotx;font-size:16px>Secret words here.</td></tr></table>', "a style attribute is written with a character reference"),
    ("a ground attribute written with a character reference not closed with ;, after a style whose reference both parsers decode alike", '<table><tr><td style="font-family:a&amp;b" bgcolor="#FBFAF6&ampx">Words.</td></tr></table>', "a bgcolor attribute is written with a character reference"),
    ("an unquoted colour attribute written with a character reference not closed with ;, after a style whose reference both parsers decode alike", '<p><font style="font-family:a&amp;b" color=#1A1A17&ampx>Words.</font></p>', "a color attribute is written with a character reference"),
    ("a style named in capitals on a tag named so, written with a character reference not closed with ;", '<P STYLE="color:#1A1A17&ampx">Ink words.</P>', "a style attribute is written with a character reference"),
    ("a single-quoted style whose reference sits past a space, which ends an unquoted value", "<p style='font-family:a b;color:#1A1A17&ampx'>Ink words.</p>", "a style attribute is written with a character reference"),
    ("a style after a / that closes the <p> for rspamd, written with a character reference not closed with ;", '<p/style="color:#1A1A17&ampx">Ink words.</p>', "a style attribute is written with a character reference"),
    ("a style after an attribute whose name begins with =, written with a character reference not closed with ;", '<p =x style="color:#1A1A17&ampx">Ink words.</p>', "a style attribute is written with a character reference"),
    ("a tag of 129 attributes, past the 128 rspamd reads, its style last, under a size rspamd reads off a family a browser drops", '<p style="font-family:x((a);font-size:1px;b)"><span ' + " ".join(f"data-a{i}" for i in range(128)) + ' style="font-size:16px">Words.</span></p>', "<span> carries more than 128 attributes"),
    ("a <p> a browser closes before a block, which rspamd holds the block in", '<p style="opacity:0.05"><div>Words.</div>', "a browser closes the <p> where rspamd opens a <div>"),
    ("an <li> a browser closes before the next, which rspamd holds the next in", "<ul><li>One.<li>Two.</ul>", "a browser closes the <li> where rspamd opens a <li>"),
    ("an end tag a browser reads as an empty <p> of its own", "<div>Words.</p></div>", "parse error (unexpected-end-tag"),
    ("text a browser moves out of a table, which rspamd keeps in it", "<table>Stray words.<tr><td>Cell words.</td></tr></table>", "a browser holds text where rspamd opens a <table>"),
    ("a / that closes a <div> for rspamd, which a browser ignores", '<div style="color:#1A1A17"/>Words.</div>', "parse error (non-void-element-with-trailing-solidus"),
    ("an unquoted value's / before the >, which closes a <span> for rspamd and is the value's in a browser", "<span title=x/>Words.</span>", "a browser holds text where rspamd closes the <span>"),
    ("a / after a tag's name, which closes a <span> for rspamd", '<span/ title="x">Words.</span>', "a browser holds text where rspamd closes the <span>"),
    ("formatting a browser opens again past an end tag out of order", "<p><b>Bold <i>both</b> italic.</i></p>", "parse error (adoption-agency-1.3"),
    ("a noscript, whose markup rspamd reads as text to an end tag", "<noscript><p>Words.</p></noscript>", "a browser opens a <p> where rspamd holds text"),
    ("a script, whose raw text rspamd ends at an end tag of any name", '<script>var a = "</b>";</script>', "<script> holds raw text"),
    ("a style element a tab in its end tag ends for a browser, not for rspamd, its sheet in a comment", '<style></style\t><!--{}p{display:none}</style>--><p>Words.</p>', "<style> holds raw text"),
    ("a style attribute named with a character reference, which rspamd decodes", '<p st&#121;le="opacity:0.05">Secret words.</p>', "is written with a character reference (st&#121;le)"),
    ("the hidden attribute named with a character reference, which rspamd decodes", "<p h&#105;dden>Secret words.</p>", "is written with a character reference (h&#105;dden)"),
    ("a style element named with a character reference, which rspamd decodes, its sheet in a comment", "<st&#121;le><!--p{display:none}--></st&#121;le><p>Words.</p>", "is written with a character reference (st&#121;le)"),
    ("a textarea, whose markup rspamd reads as markup where a browser reads text", "<textarea><b>Words.</b></textarea>", "a browser holds text where rspamd opens a <b>"),
    ("a tag rspamd holds empty, which a browser holds text in", "<nextid>Words.</nextid>", "a browser holds text where rspamd closes the <nextid>"),
    ("a tag a browser holds empty, which rspamd holds text in", "<p><bgsound>Words.</p>", "a browser closes the <bgsound> where rspamd holds text"),
    ("a column group a page leaves open, which rspamd holds the rows in", "<table><colgroup><col><tr><td>Words.</td></tr></table>", "a browser closes the <colgroup> where rspamd opens a <tr>"),
    ("a row group a page leaves open before the next, which rspamd holds the next in", "<table><thead><tr><td>Head words.</td></tr><tbody><tr><td>Words.</td></tr></tbody></table>", "a browser closes the <thead> where rspamd opens a <tbody>"),
    # Kept.
    ("a hairline cell at 1 px holding a no-break space", '<table><tr><td height="1" bgcolor="#E5E7EB" style="height:1px;background-color:#E5E7EB;font-size:1px;line-height:1px;">&nbsp;</td></tr></table>', None),
    ("an image set to display:block", '<img src="https://e.test/a.png" width="32" height="32" alt="A described image" style="display:block;">', None),
    ("the tagline's mark, its words at 18 px in a span at 5.187 px", '<span style="display:inline-block;"><span style="font-size:5.187px;line-height:0;"><span style="font-size:18px;line-height:0;">shows its work</span></span>.</span>', None),
    ("a line at line-height:0, which still paints", '<p style="line-height:0">Painted words.</p>', None),
    ("white on the button's sage", '<a href="https://e.test/x" style="background:#4F7A63;color:#ffffff;padding:12px;">Read the summary</a>', None),
    ("the muted ink on the panel", '<p style="color:#6B7280">Muted words.</p>', None),
    ("a link that sets no colour, in a browser's blue", '<a href="https://e.test/x">A link</a>', None),
    ("opacity at rspamd's floor of 0.1", '<p style="opacity:0.1">Faint words.</p>', None),
    ("half opacity", '<p style="opacity:0.5">Half shown.</p>', None),
    ("half opacity as a percentage", '<p style="opacity:50%">Half shown.</p>', None),
    ("two opacities whose product shows", '<div style="opacity:0.5"><p style="opacity:0.5">A quarter shown.</p></div>', None),
    ("two opacities whose product, 0.105, sits over the floor of 0.1 and paints the ink apart from the ground", '<div style="opacity:0.35"><p style="opacity:0.3">Faint words.</p></div>', None),
    ("ink at an alpha of 0.3 under a box at 0.35, 0.105 over the floor, which paints it apart from the ground", '<div style="opacity:0.35"><p style="color:rgba(26,26,23,0.3)">Faint words.</p></div>', None),
    ("ink at an alpha of 0.1, at the floor, which paints it apart from the ground", '<p style="color:rgba(26,26,23,0.1)">Faint words.</p>', None),
    ("a font of 4 px, rspamd's first shown size", '<p style="font-size:4px">Small words.</p>', None),
    ("0.25em, 4 px a browser's way and rspamd's", '<p style="font-size:0.25em">Small words.</p>', None),
    ("<small> under a parent at 5 px, 4.17 px in a browser", '<div style="font-size:5px"><small>Fine print.</small></div>', None),
    ("the font-size keywords and CSS-wide ones", '<p style="font-size:xx-small">A</p><p style="font-size:smaller">B</p><p style="font-size:larger">C</p><p style="font-size:initial">D</p><p style="font-size:inherit">E</p><p style="font-size:revert">F</p><p style="font:inherit">G</p>', None),
    ("the colour keywords", '<p style="color:inherit">A</p><p style="color:currentcolor">B</p><p style="color:initial">C</p><p style="color:unset">D</p>', None),
    ("the visibility keywords", '<p style="visibility:initial">A</p><p style="visibility:visible">B</p><p style="visibility:inherit">C</p><p style="visibility:unset">D</p>', None),
    ("a 4-digit hex rspamd does not read, on a colour that shows", '<p style="color:#1118">Grey words.</p>', None),
    ("the header's negative letter spacing", '<p style="letter-spacing:-0.44px">Tight words.</p>', None),
    ("a font shorthand before the longhand", '<p style="font:2px Arial;font-size:16px">Words at 16 px.</p>', None),
    ("a child that resets the size under a parent at 0", '<div style="font-size:0"><p style="font-size:16px">Words at 16 px.</p></div>', None),
    ("a child shown again under a parent rspamd reads as shown", '<div style="visibility:hidden;display:block"><span style="visibility:visible">Shown again.</span></div>', None),
    ("Outlook's own tagline in a conditional comment, which Outlook shows", "The summary that <!--[if mso]>shows its work.<![endif]--><!--[if !mso]><!--><span>shows its work.</span><!--<![endif]-->", None),
    ("mso-hide:all on a box of spaces", '<div style="mso-hide:all">&nbsp; &#8203;</div>', None),
    ("a hidden run of spaces, separators and a vertical tab, which rspamd does not count", '<p style="display:none">&nbsp;\u2028\u2029\u000b&#8203;</p>', None),
    ("a static box with no indent", '<p style="position:static;text-indent:0">Plain words.</p>', None),
    ("an open details", "<details open><summary>Shown.</summary>Unfolded words.</details>", None),
    ("a zero-width space between two words", "<p>Earnings&#8203;Nerd</p>", None),
    ("a font shorthand that sets a size and a family", '<p style="font:bold 16px/1.5 Inter,Arial">Bold words.</p>', None),
    ("ink on a ground under rspamd's alpha floor", '<div style="background:rgba(26,26,23,0.03)"><p style="color:#1A1A17">Ink words.</p></div>', None),
    ("a background-color that inherits the ground below", '<div style="background-color:#1A1A17"><p style="background-color:inherit;color:#FBFAF6">Panel on ink.</p></div>', None),
    ("the last font shorthand's size, which shows", '<p style="font:2px Arial;font:16px Arial">Words.</p>', None),
    ("a color rspamd reads over a font shorthand's colour", '<p style="color:#1A1A17;font:16px white">Words.</p>', None),
    ("rgba() of four components, which rspamd reads", '<div style="color:#FBFAF6"><p style="color:rgba(26 26 23 / 0.5)">Ink at half.</p></div>', None),
    ("a hex of eight digits, which rspamd reads", '<div style="color:#FBFAF6"><p style="color:#1A1A17FF">Ink words.</p></div>', None),
    ("ink on a ground rspamd does not read, an rgb() with an alpha", '<div style="background:rgb(26 26 23 / 0.02)"><p style="color:#1A1A17">Ink words.</p></div>', None),
    ("ruby text outside a ruby, at its parent's size", '<div style="font-size:7px"><rt>Fine print outside a ruby.</rt></div>', None),
    ("a colour attribute rspamd reads as written", '<div style="color:#FBFAF6"><font color="#1A1A17">Ink words.</font></div>', None),
    ("a hue with no unit, which rspamd reads", '<div style="color:#FBFAF6"><p style="color:hsl(60,6%,10%)">Ink words.</p></div>', None),
    ("a bgcolor in capitals on a span, which rspamd does not read and a browser paints none of", '<div style="background:#1A1A17;color:#FBFAF6"><span bgcolor="WHITE">Panel on ink.</span></div>', None),
    ("a light colour scheme in a meta", '<meta name="color-scheme" content="light"><p>Words.</p>', None),
    ("the properties that move, clip or cover no text", '<p style="font-family:Arial;font-weight:700;font-style:italic;text-align:center;text-transform:uppercase;border:1px solid #E5E7EB;border-radius:4px;padding:4px;box-sizing:border-box">Plain words.</p>', None),
    ("each property the reader reads at its inert value", '<p style="transform:none;translate:none;rotate:none;scale:none;zoom:1;clip:auto;clip-path:none;mask:none;mask-image:none;-webkit-mask:none;-webkit-mask-image:none;filter:none;mix-blend-mode:normal;contain:none;line-clamp:none;-webkit-line-clamp:none;-webkit-text-fill-color:currentcolor;background-image:none;outline:none;outline-style:none;box-shadow:none;text-shadow:none;overflow-clip-margin:0;text-decoration-thickness:auto;text-underline-offset:auto;color-scheme:light;content-visibility:visible;position:static;text-indent:0">Plain words.</p>', None),
    ("a background shorthand of none, which paints the ground below", '<div style="background:#1A1A17"><p style="background:none;color:#FBFAF6">Panel on ink.</p></div>', None),
    ("a box that clips around no counted character", '<p style="overflow:hidden">&nbsp;&#8203;</p>', None),
    ("a button's own words", "<button>Pressed words.</button>", None),
    ("a popover that sets no display, around no counted character", "<div popover>&nbsp;</div>", None),
    ("a column that sets a width, a ground of none and visibility:hidden, which leaves its cells shown", '<table><colgroup><col style="width:50%;background:none;visibility:hidden"><col></colgroup><tr><td>A words.</td><td>B words.</td></tr></table>', None),
    ("a box laid out as a table's column, set visibility:hidden, which leaves its cells shown", '<div style="display:table"><div style="display:table-column;visibility:hidden;background:none"></div><div style="display:table-row"><div style="display:table-cell">Cell words.</div></div></div>', None),
    ("an open dialog set to display:none, around no counted character", '<dialog open style="display:none">&nbsp;</dialog>', None),
    ("a decoration's line, style, colour and an automatic thickness", '<p style="text-decoration:underline dotted #6B7280 auto">Underlined words.</p>', None),
    ("a font shorthand with each word it takes before its size, a string and a generic family", '<p style="font:italic small-caps bold condensed 16px/normal &#39;Helvetica Neue&#39;, Arial, sans-serif">Styled words.</p>', None),
    ("a font shorthand with four words before its size and a family of two names", '<p style="font:normal normal normal 100 16px/1.5 a, b c">Thin words.</p>', None),
    ("a font shorthand with a line height in a viewport unit, which a browser takes", '<p style="font:16px/2vh a">Words.</p>', None),
    ("a column group set content-visibility:hidden whose column sets nothing, which leaves its cells shown", '<table><colgroup style="content-visibility:hidden"><col></colgroup><tr><td>Cell words.</td></tr></table>', None),
    ("a collapsed column under a column group the hidden attribute lays out nowhere, which leaves its cells shown", '<table><colgroup hidden><col style="visibility:collapse"></colgroup><tr><td>Cell words.</td></tr></table>', None),
    ("a font size in a unit neither reads, after an important one", '<p style="font-size:16px !important;font-size:0deg">Sized words.</p>', None),
    ("a font shorthand in a unit neither reads, after an important one", '<p style="font:16px a !important;font:0deg b">Sized words.</p>', None),
    ("an opacity rspamd scales by a unit it knows, 0.05em read as 0.8, after an important one", '<p style="opacity:1 !important;opacity:0.05em">Faded words.</p>', None),
    ("a grey hsl() rspamd reads as black, after an important ink", '<p style="color:#1A1A17 !important;color:hsl(0,0%,97%)">Ink words.</p>', None),
    ("a column group a later display lays out as a block", '<div style="display:table-column-group;display:block">Group words.</div>', None),
    ("a font shorthand's weight of 2, which rspamd does not read as its size", '<p style="font:2 16px a">Weighted words.</p>', None),
    ("a font shorthand's line height of 2px, which rspamd does not read as its size", '<p style="font:16px/2px a">Packed words.</p>', None),
    ("a negative font size rspamd reads as a percentage, after an important size", '<p style="font-size:16px !important;font-size:-50px">Sized words.</p>', None),
    ("a colour function's name rspamd loses after a number, its brackets then ending the reading, after an important ink", '<p style="color:#1A1A17 !important;color:5rgb(251,250,246)">Ink words.</p>', None),
    ("an opacity in brackets, which end rspamd's reading of the style, after an important one", '<p style="opacity:1 !important;opacity:[0.05]">Faded words.</p>', None),
    ("a colour function with a bracket among its arguments, which rspamd counts, after an important ink", '<p style="color:#1A1A17 !important;color:rgb([251,250,246)">Ink words.</p>', None),
    ("an opacity rspamd reads before a comment, which it skips, after an important one", '<p style="opacity:1 !important;opacity:0.5/*0.01*/">Faded words.</p>', None),
    ("a second semicolon, after which rspamd skips the opacity a browser drops under an important one", '<p style="opacity:1 !important;;opacity:0.05">Faded words.</p>', None),
    ("a table and its parts, to which rspamd hands no height from the box above", '<div style="height:0"><table><tr><td style="overflow:visible !important;overflow:hidden">Cell words.</td></tr></table></div>', None),
    ("a comment nested in a comment, which rspamd skips whole, after an important one", '<p style="opacity:1 !important;opacity:0.5/* /* */ 0.01 */">Faded words.</p>', None),
    ("a colour rspamd reads after a delimiter -, after an important ink", '<p style="color:#1A1A17 !important;color:#FBFAF6 -black">Ink words.</p>', None),
    ("url() after a number, which rspamd loses whole, in a family a browser drops", '<p style="opacity:0.05;font-family:5url(x);opacity:1">Faded words.</p>', None),
    ("a number of 131 bytes, whose first 127 rspamd reads, past a float's range, after an important one", '<p style="opacity:1 !important;opacity:1' + "0" * 125 + 'e-200">Faded words.</p>', None),
    ("a text indent of -999 px, short of the page's edge as rspamd reads it, in a family a browser drops", '<p style="font-family:x((a);text-indent:-999px;b)">Indented words.</p>', None),
    ("a text indent of -2000%, a percentage rspamd never reads off the page, in a family a browser drops", '<p style="font-family:x((a);text-indent:-2000%;b)">Indented words.</p>', None),
    ("a rect() with a side past 1 px, which rspamd does not read as clipping, in a family a browser drops", '<p style="font-family:x((a);clip:rect(0,2px,0,0);b)">Clipped words.</p>', None),
    ("an inset() of 49%, which rspamd does not read as clipping, in a family a browser drops", '<p style="font-family:x((a);clip-path:inset(49%);b)">Clipped words.</p>', None),
    ("a circle() of 1 px, which rspamd does not read as clipping, in a family a browser drops", '<p style="font-family:x((a);clip-path:circle(1px);b)">Clipped words.</p>', None),
    ("a clip rspamd reads a name after, which it reads as clipping nothing, in a family a browser drops", '<p style="font-family:x((a);clip:rect(0,0,0,0) auto;b)">Clipped words.</p>', None),
    ("a percentage width rspamd takes of the 10 px it reads 1% of 1024 px as, under a clip a browser does not apply", '<div style="width:1%"><p style="overflow:visible !important;overflow:hidden;width:10%">Clipped words.</p></div>', None),
    ("a height past 16 bits, which rspamd stores as 100% of its 800 px, under a clip a browser does not apply", '<p style="overflow:visible !important;overflow:hidden;height:-40000px">Clipped words.</p>', None),
    ("a hash of bytes past ASCII, whose digits rspamd counts in bytes, on a ground its characters would match", '<table><tr><td style="background-color:#00FFFF"><p style="color:#1A1A17 !important;color:#\u00e9ff">Dark words.</p></td></tr></table>', None),
    ("a colour attribute of bytes past ASCII, whose digits rspamd counts in bytes, on a ground its characters would match", '<table><tr><td style="background-color:#00FFFF"><p style="color:#1A1A17"><span color="#\u00e9ff">Dark words.</span></p></td></tr></table>', None),
    ("a name rspamd does not know before a property, after which it skips to the next ;", '<p style="foo opacity:0.05">Faded words.</p>', None),
    ("an overflow rspamd reads off its last name, visible, out of a family a browser drops", '<div style="width:0"><p style="font-family:x((a);overflow:hidden visible;b)">Clipped words.</p></div>', None),
    ("an inset() of 50 px, no percentage, which rspamd does not read as clipping, in a family a browser drops", '<p style="font-family:x((a);clip-path:inset(50px);b)">Clipped words.</p>', None),
    ("a <p> closed before a block", '<p style="opacity:0.05"></p><div>Words.</div>', None),
    ("void tags, with a closing / and without", '<p>Words<br>on<br/>lines<img src="https://e.test/a.png" alt=""/>.</p>', None),
    ("a bare column, which a browser holds in a column group it adds", '<table><col span="1"><tr><td>Words.</td></tr></table>', None),
    ("a row group written out", "<table><tbody><tr><td>Words.</td></tr></tbody></table>", None),
    ("character references left open, which a browser and rspamd read alike", "<p>Fish &amp chips &#38 peas &#; more.</p>", None),
    ("a comment between two runs of text", "<p>Words <!-- a note --> more.</p>", None),
    ("a / inside an unquoted value, short of the >", "<span title=a/b>Words.</span>", None),
    ("an end tag that closes a <p> left open in its element, before a <p> of its own", "<div><p>Words.</div><p>More words.</p>", None),
    ("a second attribute of a name, the pale one, which a browser and rspamd drop alike", '<p style="color:#1A1A17" style="color:#FBFAF6">Ink words.</p>', None),
    ("a character reference to a code point HTML maps, a Windows dash", "<p>Words &#150; more.</p>", None),
    ("a character reference to a name HTML does not define, in text", "<p>Words &foo; more.</p>", None),
    ("an attribute's value written with a character reference, which rspamd and a browser decode alike", '<p title="Fish &amp; chips">Words.</p>', None),
    ("a style written with a named reference closed with ;, which a browser and rspamd decode alike", '<p style="font-family:&quot;Inter&quot;,sans-serif">Words.</p>', None),
    ("a style written with a hex reference closed with ;, which a browser and rspamd decode alike", '<p style="font-family:&#x27;Inter&#x27;,sans-serif">Words.</p>', None),
    ("a tag of 128 attributes, all of which rspamd reads, its style last, under a size rspamd reads off a family a browser drops", '<p style="font-family:x((a);font-size:1px;b)"><span ' + " ".join(f"data-a{i}" for i in range(127)) + ' style="font-size:16px">Words.</span></p>', None),
]


def _hiding_root(html_attributes: str, body_attributes: str, fragment: str) -> str:
    """A page with a preheader, then ``fragment`` in a cell on the panel's ground that sets no colour or size of its
    own, under an html element and a body that carry the attributes given."""
    return (
        f'<!doctype html><html{html_attributes}><head><title>A head the walk reads nowhere</title></head>'
        f'<body{body_attributes} style="background-color:#F4F3EE;">'
        f'{_hidden("A line of its own.")}<table role="presentation"><tr><td style="background:#FBFAF6;">{fragment}</td></tr>'
        "</table></body></html>"
    )


# What the html element's style and the body's attributes do to every text the page holds.
HIDDEN_ROOTS = [
    ("opacity:0 on the html element", ' style="opacity:0"', "", "<p>Planted words.</p>", "<html> is opacity:0"),
    ("visibility:hidden on the html element", ' style="visibility:hidden"', "", "<p>Planted words.</p>", "visibility:hidden"),
    ("the hidden attribute on the html element", " hidden", "", "<p>Planted words.</p>", "the page hides 'Planted words.': <html> is laid out nowhere"),
    ("font-size:0 on the html element", ' style="font-size:0"', "", "<p>Planted words.</p>", "font size is 0px"),
    ("the panel's colour on the html element", ' style="color:#FBFAF6"', "", "<p>Planted words.</p>", "its colour is too like the ground"),
    ("the body's text attribute in the panel's colour", "", ' text="#FBFAF6"', "<p>Planted words.</p>", "its colour is too like the ground"),
    ("the body's link attribute in the panel's colour", "", ' link="#FBFAF6"', '<a href="https://e.test/x">A link of words.</a>', "its colour is too like the ground"),
    ("a custom property on the html element", ' style="--z:0px;font-size:var(--z)"', "", "<p>Planted words.</p>", "<html> sets font-size:var(--z)"),
    ("the body's vlink attribute", "", ' vlink="#FBFAF6"', '<a href="https://e.test/x">A link of words.</a>', "<body> sets vlink"),
    ("the body's alink attribute", "", ' alink="#FBFAF6"', '<a href="https://e.test/x">A link of words.</a>', "<body> sets alink"),
    ("a rem of an html element set to 0", ' style="font-size:0"', "", '<p style="font-size:1rem">Words at a rem.</p>', "font size is 0px"),
    ("a font shorthand's rem of an html element set to 0", ' style="font-size:0"', "", '<p style="font:1rem a">Words at a rem.</p>', "font size is 0px"),
    ("a rem of an html element set to 62.5%, at 3 px", ' style="font-size:62.5%"', "", '<p style="font-size:0.3rem">Small words.</p>', "font size is 3px"),
    ("a rem rspamd reads at 16 px, under an html element set larger", ' style="font-size:2rem"', "", '<p style="font-size:0.2rem">Small words.</p>', "rspamd reads its font size as 3px"),
    ("a clip at 0.2rem of an html element set to 100 px, 20 px", ' style="font-size:100px"', "", '<p style="max-height:0.2rem;overflow:hidden">Clipped words.</p>', "<p> sets overflow:hidden"),
    ("letter spacing of -0.09rem under an html element set to 100 px, which stacks the letters", ' style="font-size:100px"', "", '<p style="font-size:16px;letter-spacing:-0.09rem">Stacked letters.</p>', "sets letter-spacing:-0.09rem"),
    # Read stricter than a browser, which shows the text.
    ("overflow-y on the body, which a browser hands to the viewport, read stricter than a browser", "", ' style="overflow-y:hidden;height:0"', "<p>Planted words.</p>", "height:0 under overflow-y:hidden"),
    ("keyword sizes alone, which Chromium holds at 6 px, read stricter than a browser", ' style="font-size:xx-small"', "", "<p><small><small><small><small><small>Fine print.</small></small></small></small></small></p>", "font size is 3.6169px"),
    # Kept.
    ("an html element's size a paragraph resets", ' style="font-size:0"', "", '<p style="font-size:16px">Words at 16 px.</p>', None),
    ("the shell's html and a body link colour that shows", ' lang="en"', ' link="#3C6650"', '<a href="https://e.test/x">A link of words.</a>', None),
    ("an html element that clips around a body that holds no counted character", ' style="overflow:hidden"', "", "&nbsp;", None),
    ("a rem of an html element set to 62.5%, at 10 px", ' style="font-size:62.5%"', "", '<p style="font-size:1rem">Words at 10 px.</p>', None),
]


@pytest.mark.parametrize("page, expected", [(_hiding_root(*case[1:4]), case[4]) for case in HIDDEN_ROOTS], ids=[case[0] for case in HIDDEN_ROOTS])
def test_the_hidden_text_check_reads_the_html_element_and_the_body(page, expected):
    problems = hidden_text_problems(_without_preheader(page))
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"


@pytest.mark.parametrize("page, expected", [(_hiding(case[1]), case[2]) for case in HIDDEN_TEXTS], ids=[case[0] for case in HIDDEN_TEXTS])
def test_the_hidden_text_check_scores_every_planted_page(page, expected):
    problems = hidden_text_problems(_without_preheader(page))
    if expected is None:
        assert not problems, problems
    else:
        assert any(expected in problem for problem in problems), f"expected {expected!r}, got {problems}"


def test_the_rspamd_reading_reads_no_zero_in_a_unit_it_does_not_know():
    # rspamd 4.2.2 shows each text below (X_HIDDEN_CHARS 0, measured), whose value a browser drops and the reader
    # refuses: a planted case asks for the refusal alone, so this asks that no reason of rspamd's stands beside it
    for fragment in (
        '<p style="font-size:0deg">Secret words here.</p>',
        '<p style="font:0deg a">Secret words here.</p>',
        '<div style="height:0deg;overflow:hidden">Secret words here.</div>',
        # A block in brackets ends rspamd's reading, the declaration it cuts short dropped, where it nests 20 levels deep
        # or less (21 stop the reading and keep the declaration, a planted case).
        '<p style="opacity:0.05 ' + "(" * 20 + '">Secret words here.</p>',
    ):
        problems = hidden_text_problems(_without_preheader(_hiding(fragment)))
        assert problems and not any("rspamd reads" in problem for problem in problems), problems


def test_the_tree_check_closes_what_a_page_leaves_open_at_its_end():
    # A browser and rspamd alike close at the page's end each element it leaves open, and a browser reads no error in a
    # paragraph left so (a table left open is one, which the parse-error refusal holds).
    assert hidden_text_problems("<!doctype html><html><body><p>Words a page leaves open.") == []


def test_the_tree_check_counts_no_whitespace_a_browser_drops():
    # A browser drops the whitespace before <html> and <head> that rspamd's tree holds, and a run of it moves nothing a
    # filter counts: the shapes mark text only where it holds a counted character. The second page holds no whitespace
    # inside its <head>, which a browser keeps and which would join rspamd's run before <html>, so only the mark's
    # condition keeps its two shapes alike.
    for page in (
        "<!doctype html>\n<html>\n<head>\n<title>A page</title>\n</head>\n<body>\n<p>Words.</p>\n</body>\n</html>\n",
        "<!doctype html>\n<html>\n<head><title>A page</title></head>\n<body>\n<p>Words.</p>\n</body>\n</html>\n",
    ):
        assert hidden_text_problems(page) == [], page


def test_the_preheader_is_the_one_text_set_aside():
    page = _hiding("")
    assert any("laid out nowhere" in problem for problem in hidden_text_problems(page)), "read whole, the page hides its preheader"
    assert hidden_text_problems(_without_preheader(page)) == []
    second = page.replace("</div>", f'</div>{_hidden("A second line.")}', 1)
    assert hidden_text_problems(_without_preheader(second)), "a second hidden line after the preheader is not set aside with it"


# Every mail carries a text part (E110), which a client shows in place of the page, a text-only one or a watch, and a
# spam filter compares with the page (rspamd's R_PARTS_DIFFER). It says what the page says below its header: the same
# words, each link written out, the page's last line last. The one line a page shows that its text part need not is
# the one under a button that offers its link to copy, since the text part writes each link out beside the words of
# its button or link.
PAGE_ONLY = ("Can't click the button? Copy this link:",)
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
_MARKUP_IN_TEXT = re.compile(r"<[a-z!/?]|&(?:#[0-9]+|#x[0-9a-f]+|[a-z][a-z0-9]*);", re.IGNORECASE)


def _written(text: str) -> set[str]:
    """The addresses a text writes out, as a client links them: each URL, less the punctuation that ends a sentence."""
    return {url.rstrip(".,;:!?") for url in _TEXT_URL.findall(text)}


def _words(text: str) -> set[str]:
    """The words of a text, its addresses aside, in one case: what a text part and its page must share."""
    return {word.lower() for word in _WORD.findall(_TEXT_URL.sub(" ", text))}


def text_part_problems(page: str, text: object) -> list[str]:
    """Where a mail's text part does not say what its page says (E110): there is none; it leaves out a link the page
    carries, or writes out an address the page does not; its words are not the words the page shows below its header
    (``shown_text``), save the ``PAGE_ONLY`` lines; it does not end with the page's last line, the footer line; or it
    holds markup or a character reference, which a client shows as written (the inputs hand in none, so any is the
    template's). What it cannot see: whether the words come in the page's order, or a word the page and the text part
    each use in another sentence."""
    if not isinstance(text, str) or not text.strip():
        return ["the mail has no text part, so the provider builds one from the page, its preheader and header among it: "
                "return it after the page and hand it to send_email as text= (email_service._wrap_text)"]
    shown = shown_text(page)
    links = {anchor.get("href").strip() for anchor in tinyhtml5.parse(page, namespace_html_elements=False).iter("a") if anchor.get("href")}
    problems = []
    if missing := sorted(links - _written(text)):
        problems.append(f"the text part leaves out the address of a link the page carries, {missing}: write it out beside its words")
    if extra := sorted(_written(text) - links - _written(shown)):
        problems.append(f"the text part writes out an address the page does not carry: {extra}")
    page_only = shown
    for line in PAGE_ONLY:
        page_only = page_only.replace(line, " ")
    if only_page := sorted(_words(page_only) - _words(text)):
        problems.append(f"the text part leaves out words only the page shows: {only_page}")
    if only_text := sorted(_words(text) - _words(page_only)):
        problems.append(f"the text part says words only the text part says: {only_text}")
    last = shown.splitlines()[-1] if shown else ""
    if " ".join(text.split()[-len(last.split()):]) != last:
        problems.append(f"the text part does not end as the page does, with {last!r}")
    if _MARKUP_IN_TEXT.search(text):
        problems.append("the text part holds markup or a character reference, which a client shows as written: write it as plain text")
    return problems


def test_every_mail_carries_a_text_part_that_says_what_its_page_says(rendered):
    mails = [(name, page, text) for name, pairs in rendered["mails"].items() for page, text in pairs]
    assert {name for name, _, _ in mails} == set(RENDERS), (
        "a render built no page with a text part beside it: a render or build function returns its text part after its "
        "page, and a send_ function hands send_email both"
    )
    problems = [f"{name}: {problem}" for name, page, text in mails for problem in text_part_problems(page, text)]
    assert not problems, "\n".join(sorted(set(problems)))


_TEXT_PAGE_BODY = (
    '<p style="margin:0 0 16px;">Hi Sam,</p><p style="margin:0 0 16px;">Your report is ready — read it today.</p>'
    '<p><a href="https://e.test/report" style="color:#3C6650;">Read the report</a></p>'
    '<p style="color:#6B7280;">Can&apos;t click the button? Copy this link:<br>https://e.test/report</p>'
)
_TEXT_FOOTER = 'You asked for it. <a href="https://e.test/settings" style="color:#3C6650;">Settings</a>.'
_TEXT_PART = (
    "Hi Sam,\n\nYour report is ready: read it today.\n\nRead the report: https://e.test/report\n\n"
    "You asked for it. Settings (https://e.test/settings).\n\n" + email_service._FOOTER_LINE
)


def _text_page() -> str:
    return email_service._wrap_html(_TEXT_PAGE_BODY, _TEXT_FOOTER, preheader="Your report is ready.")


# Each way a text part can fail to say what its page says, and the look-alikes that say it.
TEXT_PARTS = [
    # Broken.
    ("no text part", None, "has no text part"),
    ("a blank text part", " \n ", "has no text part"),
    ("a text part that leaves out the button's link", _TEXT_PART.replace("Read the report: https://e.test/report", "Read the report"), "leaves out the address"),
    ("a text part that leaves out the footer's link", _TEXT_PART.replace(" (https://e.test/settings)", ""), "leaves out the address"),
    ("a text part with an address the page does not carry", _TEXT_PART.replace("https://e.test/report", "https://e.test/elsewhere"), "does not carry"),
    ("a text part that leaves out a sentence", _TEXT_PART.replace("Your report is ready: read it today.\n\n", ""), "words only the page shows"),
    ("a text part that adds a sentence", _TEXT_PART.replace("Hi Sam,", "Hi Sam,\n\nAct now."), "words only the text part says"),
    ("a text part that leaves out the footer line", _TEXT_PART.replace("\n\n" + email_service._FOOTER_LINE, ""), "does not end as the page does"),
    ("a text part with the footer line first", email_service._FOOTER_LINE + "\n\n" + _TEXT_PART.replace("\n\n" + email_service._FOOTER_LINE, ""), "does not end as the page does"),
    ("a text part that holds a tag", _TEXT_PART.replace("ready", "<strong>ready</strong>"), "holds markup"),
    ("a text part that holds a character reference", _TEXT_PART.replace("Sam,", "Sam&apos;s,"), "holds markup"),
    # Kept.
    ("the text part as email_service writes one", _TEXT_PART, None),
    ("a link's address before the full stop that ends its sentence", _TEXT_PART.replace("https://e.test/report\n", "https://e.test/report.\n"), None),
    ("other punctuation, a comma for the page's dash", _TEXT_PART.replace("ready: read", "ready, read"), None),
]


@pytest.mark.parametrize("text, expected", [case[1:] for case in TEXT_PARTS], ids=[case[0] for case in TEXT_PARTS])
def test_the_text_part_check_scores_every_planted_text(text, expected):
    problems = text_part_problems(_text_page(), text)
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
        "HIDDEN_TEXTS": (sum(isinstance(case[-1], str) for case in HIDDEN_TEXTS), sum(case[-1] is None for case in HIDDEN_TEXTS)),
        "HIDDEN_ROOTS": (sum(isinstance(case[-1], str) for case in HIDDEN_ROOTS), sum(case[-1] is None for case in HIDDEN_ROOTS)),
        "TEXT_PARTS": (sum(isinstance(case[-1], str) for case in TEXT_PARTS), sum(case[-1] is None for case in TEXT_PARTS)),
        "CONTRASTS": (sum(isinstance(case[-1], str) for case in CONTRASTS), sum(case[-1] is None for case in CONTRASTS)),
    }
    assert counts == {
        "PAGES": (12, 8), "REACHES": (10, 4), "SENDS": (50, 18), "ADDRESSES": (63, 9), "SENT": (11, 1), "PREHEADERS": (21, 7),
        "HIDDEN_TEXTS": (400, 105), "HIDDEN_ROOTS": (18, 4), "TEXT_PARTS": (11, 3), "CONTRASTS": (81, 29),
    }, "a planted case was added or dropped: keep these counts equal to the lists in the same diff"
    for name, cases in (
        ("PAGES", PAGES), ("REACHES", REACHES), ("SENDS", SENDS), ("ADDRESSES", ADDRESSES), ("SENT", SENT), ("PREHEADERS", PREHEADERS),
        ("HIDDEN_TEXTS", HIDDEN_TEXTS), ("HIDDEN_ROOTS", HIDDEN_ROOTS), ("TEXT_PARTS", TEXT_PARTS), ("CONTRASTS", CONTRASTS),
    ):
        labels = [case[0] for case in cases]
        assert len(set(labels)) == len(labels), f"each case {name} plants has a name of its own"


if __name__ == "__main__":  # the renders, in an interpreter of their own (the mail fixture and the planted stubs')
    print(json.dumps(_planted_sends() if sys.argv[1:] == ["planted"] else _render(RENDERS)))
