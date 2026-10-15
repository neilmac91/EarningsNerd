"""Gate: an address a rendered mail carries into the site's files is a registered path on FRONTEND_URL.

``test_mail_published_assets.py`` reads the code that builds mail, and cannot follow a value through it.
This gate reads the mail that code builds, so an address is checked however the code derived it: a
``.replace``, an alias, a join, a fill or a rebinding (``frontend/public/assets/LOGO_README.md`` ›
Published URLs stay put).

It renders every function in ``backend/app`` that calls ``email_service._wrap_html``, with
``FRONTEND_URL`` set to a sentinel that keeps its trailing slash. Then it reads every address in each
page and in its plain-text copy:
- each attribute that holds one, ``srcset`` candidate by candidate, with entities decoded;
- each CSS ``url()``, in a ``style`` attribute or a ``<style>`` block;
- the markup inside Outlook's conditional comments;
- every absolute URL in the text.

Each address that points into the site's files must be a whole registered path
(``frontend/tests/unit/publishedAssetUrls.json``), its query and fragment aside. The site's files are a
directory or a root file under ``frontend/public``. Each such address must also be built on
``FRONTEND_URL`` with that slash stripped:
- on no other origin of the site's (``earningsnerd.io`` or a host under it);
- never without an origin, since a mail has no base URL;
- never after a doubled slash, which answers 308.

It sees only what these inputs render. Two things are left to the code scan:
- a branch these inputs do not take;
- mail built without ``_wrap_html``: ``routers/contact.py``'s confirmation (E56), and the internal admin
  and team notices.
"""
import ast
import asyncio
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from app.config import settings
from app.services import email_service

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
APP = BACKEND / "app"
PUBLIC = REPO / "frontend" / "public"
REGISTER = json.loads((REPO / "frontend" / "tests" / "unit" / "publishedAssetUrls.json").read_text(encoding="utf-8"))
REGISTERED = frozenset(entry["url"] for entry in REGISTER["paths"])
SITE_NAMES = frozenset(p.name for p in PUBLIC.iterdir() if not p.name.startswith("."))
SENTINEL = "https://frontend.example.test/"  # FRONTEND_URL with a trailing slash, which a value may keep
SENTINEL_HOST = urlsplit(SENTINEL).hostname
BUILT_ON = SENTINEL.rstrip("/") + "/"
TILE = f"{SENTINEL.rstrip('/')}/assets/earningsnerd-appicon.png"

TO = "recipient@example.com"
LINK = "https://e.test/t"
ALERT = dict(name="Ada", company_name="Acme Corp", ticker="ACME", filing_type="10-K", filing_date="2026-01-01")
DIGEST_ITEM = {"company_name": "Acme Corp", "ticker": "ACME", "filing_type": "10-K", "filing_date": "2026-01-01"}
CLEAN_REPORT = {"ticker_mismatches": [], "ticker_not_in_file": [], "coverage_gaps": [], "filing_anomalies": [], "partial_reasons": []}

# Each function that calls _wrap_html, with inputs that take each branch that puts an address in its page.
RENDERS = {
    "render_welcome_email": [dict(name="Ada", position=3, referral_link=LINK, verification_link=LINK)],
    "render_referral_success_email": [dict(name="Ada", new_position=2, referral_link=LINK)],
    "send_verification_email": [dict(to_email=TO, name="Ada", verification_link=LINK)],
    "send_invite_email": [dict(to_email=TO, magic_link=LINK)],
    "send_password_reset_email": [dict(to_email=TO, name="Ada", reset_link=LINK)],
    "send_oauth_linked_email": [dict(to_email=TO, name="Ada", provider="Google")],
    "send_account_exists_email": [dict(to_email=TO, name="Ada", login_link=LINK, reset_link=LINK)],
    "render_new_filing_alert": [
        dict(ALERT, filing_id=1, wording_changes={"has_changes": True, "items_total": 3}),
        dict(ALERT, filing_url=LINK),
        dict(ALERT),
    ],
    "render_daily_digest": [dict(name="Ada", items=[dict(DIGEST_ITEM, filing_id=1), dict(DIGEST_ITEM, filing_url=LINK), DIGEST_ITEM])],
    "render_data_quality_report": [dict(report=CLEAN_REPORT)],
    "render_earnings_day_alert": [dict(name="Ada", items=[{"ticker": "ACME", "company_name": "Acme Corp", "time": "bmo"}])],
}

# Attributes that hold an address, VML's included (Outlook's images and fills).
_URL_ATTRIBUTES = {"src", "href", "background", "poster", "action", "formaction", "cite", "longdesc", "data", "xlink:href", "o:href"}
_CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)""", re.IGNORECASE | re.DOTALL)
_TEXT_URL = re.compile(r"""(?:https?:)?//[^\s"'<>()]+""", re.IGNORECASE)


def _srcset(value: str) -> list[str]:
    """The candidates' addresses, parsed as HTML parses a srcset: an address, then descriptors to a comma."""
    found, i = [], 0
    while i < len(value):
        while i < len(value) and (value[i].isspace() or value[i] == ","):
            i += 1
        start = i
        while i < len(value) and not value[i].isspace():
            i += 1
        address = value[start:i]
        if address.endswith(","):
            found.append(address.rstrip(","))
            continue
        if address:
            found.append(address)
        depth = 0
        while i < len(value) and not (value[i] == "," and depth == 0):
            depth += (value[i] == "(") - (value[i] == ")")
            i += 1
    return found


class _Addresses(HTMLParser):
    """Every address a page carries, as a client reads it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value is None:
                continue
            if name == "srcset":
                self.found += _srcset(value)
            elif name in _URL_ATTRIBUTES:
                self.found.append(value.strip())
            elif name == "style":
                self.found += [match.group(2).strip() for match in _CSS_URL.finditer(value)]

    handle_startendtag = handle_starttag

    def handle_data(self, data):
        self.found += [match.group(0).rstrip(".,;:!?") for match in _TEXT_URL.finditer(data)]
        self.found += [match.group(2).strip() for match in _CSS_URL.finditer(data)]

    def handle_comment(self, data):
        # Outlook's conditional comments hold markup of their own.
        self.found += addresses(data)


def addresses(page: str) -> list[str]:
    parser = _Addresses()
    parser.feed(page)
    parser.close()
    return parser.found


def _resolved(path: str) -> str:
    """The path a client requests: percent-escapes decoded and dot segments removed (RFC 3986 § 5.2.4)."""
    out: list[str] = []
    segments = unquote(path).split("/")
    for i, segment in enumerate(segments):
        if segment == "..":
            if len(out) > 1:
                out.pop()
        elif segment != ".":
            out.append(segment)
        if segment in (".", "..") and i == len(segments) - 1:
            out.append("")
    return "/".join(out)


def problem(address: str) -> str | None:
    """What is wrong with an address into the site's files, or None when it is right or points elsewhere."""
    parts = urlsplit(address)
    host = (parts.hostname or "").lower()
    site = host == SENTINEL_HOST or host == "earningsnerd.io" or host.endswith(".earningsnerd.io")
    if (parts.netloc and not site) or parts.scheme not in ("", "http", "https"):
        return None  # another site's address, or mailto:, tel:, cid:
    path = _resolved(parts.path)
    if path.lstrip("/").split("/", 1)[0] not in SITE_NAMES:
        return None  # a page of the site's, not one of its files
    if not parts.netloc:
        return "has no origin, and a mail has no base URL: build it on FRONTEND_URL"
    if host != SENTINEL_HOST:
        return "is on an origin of the site's other than FRONTEND_URL: build it on FRONTEND_URL"
    if parts.path.startswith("//"):
        return "keeps FRONTEND_URL's trailing slash, and a doubled slash answers 308: strip it"
    if not address.startswith(BUILT_ON):
        return "is not built on FRONTEND_URL as it is set"
    if parts.path not in REGISTERED:
        return "is not a whole registered path (frontend/tests/unit/publishedAssetUrls.json), spelled as registered"
    return None


def _callers() -> set[str]:
    """Every function in backend/app that calls _wrap_html, named as RENDERS names it."""
    found = set()
    for path in sorted(APP.rglob("*.py")):
        for function in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(function):
                callee = node.func if isinstance(node, ast.Call) else None
                if getattr(callee, "id", None) == "_wrap_html" or getattr(callee, "attr", None) == "_wrap_html":
                    found.add(function.name if path == APP / "services" / "email_service.py" else f"{path.relative_to(APP)}::{function.name}")
    return found


def _pages(monkeypatch) -> dict[str, list[str]]:
    """Each function's pages and plain-text copies, rendered on the sentinel."""
    monkeypatch.setattr(settings, "FRONTEND_URL", SENTINEL)
    sent: list[str] = []

    async def _record(to, subject, html, *args, **kwargs):
        sent.append(html)
        return {"id": "msg_test"}

    monkeypatch.setattr(email_service, "send_email", _record)
    pages: dict[str, list[str]] = {}
    for name, cases in RENDERS.items():
        function = getattr(email_service, name)
        for kwargs in cases:
            if asyncio.iscoroutinefunction(function):
                asyncio.run(function(**kwargs))
                pages.setdefault(name, []).append(sent.pop())
            else:
                pages.setdefault(name, []).extend(function(**kwargs))
    return pages


def test_every_function_that_wraps_a_mail_is_rendered_here():
    assert _callers() == set(RENDERS), (
        "render each function that calls _wrap_html here, with inputs for each branch that puts an address in its page"
    )


def test_every_rendered_address_into_the_sites_files_is_registered_and_built_on_frontend_url(monkeypatch):
    problems = []
    for name, pages in _pages(monkeypatch).items():
        found = [address for page in pages for address in addresses(page)]
        assert TILE in found, f"{name}: the header's tile is not among the addresses read: the reader has narrowed"
        problems += [f"{name}: {address} {wrong}" for address in found if (wrong := problem(address))]
    assert not problems, (
        "a rendered mail addresses a file of the site's other than by a whole registered path on FRONTEND_URL. "
        "Register a path mail shows in frontend/tests/unit/publishedAssetUrls.json in the same PR, and build its "
        "address on settings.FRONTEND_URL.rstrip('/') (LOGO_README.md > Published URLs stay put):\n" + "\n".join(problems)
    )


def _img(src: str) -> str:
    return f'<td><img src="{src}" width="32" alt=""></td>'


# Each way a page can carry an address into the site's files, and the look-alikes that must pass.
ADDRESSES = [
    # Flagged.
    ("an unregistered file", _img(f"{BUILT_ON}assets/earningsnerd-appicon@2x.png"), "not a whole registered path"),
    ("a srcset's second candidate", f'<img src="{TILE}" srcset="{TILE} 1x, {BUILT_ON}assets/earningsnerd-appicon@2x.png 2x">', "not a whole registered path"),
    ("a srcset with no space after its comma", f'<img srcset="{TILE} 1x,{BUILT_ON}assets/x@2x.png 2x">', "not a whole registered path"),
    ("an entity in the path", _img(f"{BUILT_ON}assets/earningsnerd-appicon&#64;2x.png"), "not a whole registered path"),
    ("a suffix a client reads into the path", _img(f"{TILE}(1)"), "not a whole registered path"),
    ("a CSS url() in a style attribute", f"<td style=\"background:url('{BUILT_ON}assets/x.png')\"></td>", "not a whole registered path"),
    ("a CSS url() in a style block", f"<style>.x{{background-image:url({BUILT_ON}assets/x.png)}}</style>", "not a whole registered path"),
    ("an image inside Outlook's conditional comment", f'<!--[if mso]><v:image src="{BUILT_ON}assets/x.png" /><![endif]-->', "not a whole registered path"),
    ("a VML fill inside Outlook's conditional comment", f'<!--[if gte mso 9]><v:fill type="tile" src="{BUILT_ON}icons/x.png" /><![endif]-->', "not a whole registered path"),
    ("a link to a file", f'<a href="{BUILT_ON}icons/icon-192.png">icon</a>', "not a whole registered path"),
    ("a root file", f'<link rel="icon" href="{BUILT_ON}favicon.ico">', "not a whole registered path"),
    ("an address in the plain-text copy", f'<pre style="display:none">See {BUILT_ON}assets/x.png.</pre>', "not a whole registered path"),
    ("a dot segment", _img(f"{BUILT_ON}./assets/earningsnerd-appicon.png"), "spelled as registered"),
    ("a parent segment", _img(f"{BUILT_ON}icons/../assets/earningsnerd-appicon.png"), "spelled as registered"),
    ("a percent-escape", _img(f"{BUILT_ON}%61ssets/earningsnerd-appicon.png"), "spelled as registered"),
    ("a relative path", _img("/assets/earningsnerd-appicon.png"), "has no origin"),
    ("www hard-coded", _img("https://www.earningsnerd.io/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("the apex, protocol-relative", _img("//earningsnerd.io/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("the API host", _img("https://api.earningsnerd.io/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("a host in capitals", _img("https://WWW.EarningsNerd.io/assets/earningsnerd-appicon.png"), "an origin of the site's other than FRONTEND_URL"),
    ("FRONTEND_URL unstripped", _img(f"{SENTINEL}/assets/earningsnerd-appicon.png"), "keeps FRONTEND_URL's trailing slash"),
    ("FRONTEND_URL on another scheme", _img(f"http://{SENTINEL_HOST}/assets/earningsnerd-appicon.png"), "not built on FRONTEND_URL"),
    # Pass.
    ("the tile on FRONTEND_URL", _img(TILE), None),
    ("a registered path with a query and a fragment", _img(f"{TILE}?v=2#top"), None),
    ("a page of the site's", f'<a href="{BUILT_ON}dashboard/settings">Settings</a>', None),
    ("another site's file", _img("https://cdn.example.com/assets/x.png"), None),
    ("a mail link", '<a href="mailto:support@earningsnerd.io">Write to us</a>', None),
    ("a sentence's full stop after the tile, in text", f"<p>The tile is {TILE}.</p>", None),
]


@pytest.mark.parametrize("page, expected", [form[1:] for form in ADDRESSES], ids=[form[0] for form in ADDRESSES])
def test_the_reader_scores_every_planted_address(page, expected):
    found = addresses(page)
    assert found, "the reader found no address"
    verdicts = [wrong for address in found if (wrong := problem(address))]
    if expected is None:
        assert not verdicts, verdicts
    else:
        assert any(expected in wrong for wrong in verdicts), f"expected {expected!r}, got {verdicts} from {found}"
