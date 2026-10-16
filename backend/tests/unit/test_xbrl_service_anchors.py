"""Wave 0 anchors (X0) for the xbrl_service hot-module refactor (tasks/refactor-plan-2026-10.md, M5).

Characterization tests that pin today's behaviour at the seams the refactor cuts: X1 moves the
two-tier cache, X2 the companyfacts fallback, X3 the standardized metrics, X4 the filing-instance
extractor, X5 the sections extractor. A move or split that changes what these pin fails here.

Every boundary is faked in-process on a SHARED object, so the fakes keep intercepting wherever the
reading code moves: ``httpx.AsyncClient``, the ``sec_rate_limiter`` singleton, ``settings``,
``asyncio.wait_for`` (read by ``edgar/async_executor.py`` at call time) and the edgartools
``Company`` behind ``edgar/client.py``'s by-accession resolver, and the edgartools ``HTMLParser`` and
``CrossReferenceIndex`` classes the section parse reads. No test patches a name on xbrl_service's
module namespace; X0.5 patches attributes of a throwaway ``EdgarXBRLService()``.
"""

import asyncio
import json
import threading
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from edgar.documents import CrossReferenceIndex, HTMLParser

from app.config import settings
from app.utils.datetimes import utcnow
from app.services.edgar import client as edgar_client
from app.services.edgar import xbrl_service
from app.services.edgar.circuit_breaker import edgar_circuit_breaker
from app.services.edgar.config import EDGAR_IDENTITY
from app.services.edgar.instance_extractor import SEGMENT_AXIS
from app.services.edgar.xbrl_service import (
    EdgarXBRLService,
    _cache_set_sync,
    _extract_from_filing_instance_sync,
    clear_xbrl_cache,
    get_xbrl_cache_stats,
)
from app.services.sec_rate_limiter import sec_rate_limiter

pytestmark = pytest.mark.unit

CIK, CIK10, ACC = "320193", "0000320193", "0000320193-25-000079"
POR = "2025-09-27"  # 10-K period of report; both spans below are 363 days (10-K window 320-390)
CUR, PRI = ("2024-09-29", "2025-09-27"), ("2023-10-01", "2024-09-28")


# ---------------------------------------------------------------------------
# Fakes: the edgartools objects (Company -> Filing -> XBRL facts query / document object)
# ---------------------------------------------------------------------------

class _Frame:
    """The two DataFrame members instance_extractor reads: ``empty`` and ``to_dict("records")``."""

    def __init__(self, records, broken=False):
        self._records, self._broken = records, broken
        self.empty = not records and not broken

    def to_dict(self, orient):
        # Records are the only shape the extractor loops consume; another orientation would hand
        # them a dict of columns from a real DataFrame (instance_extractor.py:236, :689, :825).
        assert orient == "records", f"to_dict({orient!r}): the extractor reads frames as records"
        if self._broken:
            raise RuntimeError("frame failed to materialise")
        return [dict(row) for row in self._records]


class _Query:
    def __init__(self, xb):
        self._xb, self._concept, self._axis = xb, None, None

    def by_concept(self, concept, exact=False):
        # edgartools matches by regex unless exact=True, which would pull in longer tags that
        # start with the concept (instance_extractor.py:231, :682, :817 all pass exact=True).
        assert exact is True, f"by_concept({concept!r}) without exact=True matches by regex in edgartools"
        self._concept = concept
        return self

    def by_dimension(self, axis, value=None):  # noqa: ARG002
        self._axis = axis
        return self

    def to_dataframe(self):
        rows = self._xb.rows.get(self._concept, [])
        if self._axis is not None:
            rows = [row for row in rows if any(self._axis in key for key in row)]
        return _Frame(rows, broken=(self._concept, self._axis) in self._xb.broken)


class _XBRL:
    """``xb.facts.query().by_concept(c, exact=True)[.by_dimension(axis)].to_dataframe()``.

    Like edgartools, a plain concept query returns every fact (dimensioned ones included) and a
    ``by_dimension`` query keeps the facts tagged on that axis. ``broken`` names the
    (concept, axis-or-None) queries whose frame fails to materialise.
    """

    def __init__(self, rows, broken=()):
        self.rows, self.broken = rows, set(broken)
        self.facts = SimpleNamespace(query=lambda: _Query(self))


class _Filing:
    def __init__(self, form, period_of_report=POR, xb=None):
        self.form, self.period_of_report = form, period_of_report
        self._xb = xb

    def xbrl(self):
        return self._xb


@pytest.fixture
def fake_edgar(monkeypatch):
    """The edgartools Company behind ``client.resolve_filing_by_accession``; its cache is isolated."""
    calls, filings = [], {}

    class FakeCompany:
        sic = "3571"  # non-financial: the as-reported statement path declines before reading `xb`

        def __init__(self, cik):
            calls.append(("company", cik))

        def get_filings(self, accession_number=None, trigger_full_load=None):  # noqa: ARG002
            calls.append(("filings", accession_number))
            return [filings[accession_number]] if accession_number in filings else []

    monkeypatch.setattr(edgar_client, "EdgarCompany", FakeCompany)
    monkeypatch.setattr(edgar_client, "_company_cache", {})
    return SimpleNamespace(calls=calls, filings=filings)


def _fact(span, value, currency="USD", **extra):
    start, end = span
    return {"is_dimensioned": False, "period_start": start, "period_end": end,
            "numeric_value": value, "currency": currency, **extra}


def _segment_fact(member, span, value):
    return _fact(span, value, is_dimensioned=True, dimension_member_label=member,
                 **{f"dim_us-gaap_{SEGMENT_AXIS}": f"acme:{member}Member"})


# ---------------------------------------------------------------------------
# X0.1 — companyfacts fallback transport (X2 moves it to xbrl_companyfacts.py)
# ---------------------------------------------------------------------------

COMPANYFACTS = Path(__file__).resolve().parents[1] / "fixtures" / "companyfacts_sample.json"
FACTS_CIK, FACTS_ACC = "0001789012", "0001789012-24-000031"  # the recorded payload's own target 10-K
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001789012.json"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 203, 404, 429, 503])
async def test_x0_1_companyfacts_transport(monkeypatch, status):
    """X0.1 — backend/app/services/edgar/xbrl_service.py:850-889 (CLAUDE.md rule 5).

    A bare ``httpx.AsyncClient()`` context (:873) makes ONE GET of the companyfacts URL with
    ``User-Agent: EDGAR_IDENTITY`` and ``timeout=30.0`` (:875-879) inside ONE
    ``sec_rate_limiter.execute`` single token wait, never ``execute_with_backoff`` (:883, comment
    :868-872), and never through the edgar circuit breaker; a non-2xx is None via
    ``raise_for_status`` and the outer except (:880, :887-889); a 2xx body goes unchanged to
    ``_parse_company_facts`` with the requested accession (:884-885). ``raise_for_status`` passes
    every 2xx, so a 203 is parsed like a 200, as the comment says; pinned as it is today.
    Today the method is only ever patched away (test_accession_xbrl_extraction.py:416,430,448;
    evals/acceptance_archive.py:630).
    """
    payload = json.loads(COMPANYFACTS.read_text())
    events = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            events.append(("client", args, kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            events.append(("closed",))
            return False

        async def get(self, url, **kwargs):
            events.append(("get", url, kwargs))
            return httpx.Response(status, json=payload, request=httpx.Request("GET", url))

    async def execute(request_fn):
        events.append(("execute",))
        return await request_fn()

    async def execute_with_backoff(request_fn, *args, **kwargs):
        events.append(("execute_with_backoff",))
        return await request_fn()

    # settings.SEC_USER_AGENT shares EDGAR_IDENTITY's default; make them differ so the header's
    # SOURCE is pinned, not a coincidence of equal defaults.
    monkeypatch.setattr(settings, "SEC_USER_AGENT", "settings-user-agent (must not be sent here)")
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    breaker_requests = edgar_circuit_breaker.stats.total_requests
    with patch.object(sec_rate_limiter, "execute", execute), \
         patch.object(sec_rate_limiter, "execute_with_backoff", execute_with_backoff):
        result = await EdgarXBRLService()._fallback_to_company_facts(FACTS_CIK, FACTS_ACC)

    assert events == [
        ("client", (), {}),
        ("execute",),
        ("get", FACTS_URL, {"headers": {"User-Agent": EDGAR_IDENTITY}, "timeout": 30.0}),
        ("closed",),
    ]
    assert edgar_circuit_breaker.stats.total_requests == breaker_requests
    if 200 <= status < 300:
        expected = EdgarXBRLService()._parse_company_facts(payload, FACTS_ACC)
        assert result == expected
        # Non-vacuous: the recorded payload yields facts, all from the requested filing.
        assert expected["revenue"] and {point["accn"] for point in expected["revenue"]} == {FACTS_ACC}
    else:
        assert result is None


# ---------------------------------------------------------------------------
# X0.2 — summary sections parsed from the fetched primary document (X5; E28)
# ---------------------------------------------------------------------------

class _Section:
    """An edgartools Section: ``.text()`` is a method in 5.36+, a plain str in other versions."""

    def __init__(self, text, method=True):
        self.text = (lambda: text) if method else text


class _RaisingSections(dict):
    def get(self, key, default=None):  # noqa: ARG002
        raise RuntimeError("sections exploded")


class _UnreadableSection:
    """A section whose text cannot be read, as every 10-K item was behind SEC's 2026-10 403."""

    def text(self):
        raise AttributeError("'NoneType' object has no attribute 'download'")


HTML = "<html><body>the primary document the pipeline fetched</body></html>"
# Long enough to pass the stub filter, so reading the WRONG key shows up.
_WRONG_KEY = "wrong key " * 30
SECTIONS_10K = {
    "part_i_item_1a": _Section("\n  " + "r" * 250 + "  \n"),
    "part_i_item_7": _Section(_WRONG_KEY),  # Item 7 belongs to Part II: never read from Part I
    "part_ii_item_8": _Section("f" * 200),
}
SECTIONS_10Q = {
    "part_i_item_1": _Section("\n" + "F" * 300 + "  "),  # returned stripped
    "part_i_item_2": _Section("M" * 300, method=False),
    "part_ii_item_1a": _Section("  " + "R" * 199 + "  "),  # 203 raw, 199 stripped: a stub
    "part_ii_item_2": _Section(_WRONG_KEY),  # Part II Item 2 is not MD&A
}
SECTIONS_20F = {
    "part_i_item_3": _Section("K" * 300),
    "part_i_item_5": _Section("O" * 300),
    "part_iii_item_18": _Section("S" * 150),  # stub: falls through to the next candidate
    "part_iii_item_17": _Section(" " + "E" * 300 + "\n"),  # returned stripped
    "part_i_item_8": _Section("G" * 300),  # a later candidate is never read once one wins
}
SECTIONS_STUBS = {"part_i_item_1a": _Section("r" * 199), "part_ii_item_7": _Section(""),
                  "part_ii_item_8": _Section("f" * 199)}


@pytest.fixture
def executor_waits(monkeypatch):
    """Timeouts handed to ``asyncio.wait_for`` for local-parse work (``run_parse_with_timeout``)."""
    real_wait_for, waits = asyncio.wait_for, []

    async def spy(aw, timeout=None):
        if getattr(getattr(aw, "cr_code", None), "co_name", None) == "run_executor_work":
            waits.append(timeout)
        return await real_wait_for(aw, timeout)

    monkeypatch.setattr(asyncio, "wait_for", spy)
    return waits


@pytest.fixture
def parser(monkeypatch):
    """The shared edgartools parser, ``HTMLParser(ParserConfig(form)).parse(html).sections``, and the
    Cross Reference Index some 10-K filers use instead of item headings."""
    state = SimpleNamespace(sections={}, error=None, seen=[], threads=[], index_items={}, index_built=0)
    real_parse = HTMLParser.parse

    def parse(self, html):
        if html != HTML:  # ``parse_html`` converting a Cross Reference Index item: the real parser
            return real_parse(self, html)
        state.seen.append((self.config.form, html))
        state.threads.append(threading.current_thread().name)
        if state.error is not None:
            raise state.error
        return SimpleNamespace(sections=state.sections)

    def has_index(self):
        state.index_built += 1
        return bool(state.index_items)

    monkeypatch.setattr(HTMLParser, "parse", parse)
    monkeypatch.setattr(CrossReferenceIndex, "has_index", has_index)
    monkeypatch.setattr(CrossReferenceIndex, "extract_item_content", lambda self, item: state.index_items.get(item))
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize(("filing_type", "service_timeout", "wait", "sections", "expected", "parsed_as"), [
    ("10-K", 15.0, 30.0, SECTIONS_10K, {"risk": "r" * 250, "financials": "f" * 200}, "10-K"),
    ("10-K/A", 45.0, 45.0, SECTIONS_10K, {"risk": "r" * 250, "financials": "f" * 200}, "10-K"),
    ("10-Q", 15.0, 30.0, SECTIONS_10Q, {"financials": "F" * 300, "mda": "M" * 300}, "10-Q"),
    ("10-Q", 35.0, 35.0, SECTIONS_10Q, {"financials": "F" * 300, "mda": "M" * 300}, "10-Q"),
    ("20-F", 15.0, 40.0, SECTIONS_20F, {"risk": "K" * 300, "mda": "O" * 300, "financials": "E" * 300}, "20-F"),
    ("20-F/A", 35.0, 40.0, SECTIONS_20F, {"risk": "K" * 300, "mda": "O" * 300, "financials": "E" * 300}, "20-F"),
    ("20-F", 45.0, 45.0, SECTIONS_20F, {"risk": "K" * 300, "mda": "O" * 300, "financials": "E" * 300}, "20-F"),
    ("10-K", 15.0, 30.0, SECTIONS_STUBS, None, "10-K"),
], ids=["10-K", "10-K/A-long-timeout", "10-Q", "10-Q-mid-timeout", "20-F", "20-F/A-mid-timeout",
        "20-F-long-timeout", "all-stubs"])
async def test_x0_2_filing_sections_per_form_and_timeout(
    fake_edgar, executor_waits, parser, filing_type, service_timeout, wait, sections, expected, parsed_as,
):
    """X0.2 — ``get_filing_sections`` parses the HTML it is handed with the form's base config
    (amendments normalized) and makes no SEC request: no filing resolution and no breaker traffic.
    10-K items by canonical part key (a Part I Item 7 is never MD&A), 10-Q part-qualified keys with
    ``.text`` as method or str, 20-F ordered candidates where the first real one wins; text is
    stripped and kept only at ``>= _SECTION_MIN_CHARS``; nothing usable is None, not {}. The plain
    executor waits ``max(timeout, 40.0)`` for a 20-F and ``max(timeout, 30.0)`` otherwise."""
    parser.sections = sections
    breaker_requests = edgar_circuit_breaker.stats.total_requests

    result = await EdgarXBRLService(timeout=service_timeout).get_filing_sections(ACC, filing_type, html=HTML)

    assert result == expected
    assert parser.seen == [(parsed_as, HTML)]
    assert [name.rsplit("_", 1)[0] for name in parser.threads] == ["edgar_parse"]  # not the SEC pool
    assert executor_waits == [wait]
    assert fake_edgar.calls == []
    assert edgar_circuit_breaker.stats.total_requests == breaker_requests


def _ten_k_mda(**keys):
    return {"part_i_item_1a": _Section("r" * 250), "part_ii_item_8": _Section("f" * 250), **keys}


@pytest.mark.asyncio
@pytest.mark.parametrize(("sections", "index_items", "mda", "index_built"), [
    (_ten_k_mda(part_ii_item_7=_Section("P" * 250), part_ii_items_6_and_7=_Section("C" * 250)), {}, "P" * 250, 0),
    (_ten_k_mda(part_ii_item_7=_Section("   "), part_ii_items_6_and_7=_Section("C" * 250)), {}, "C" * 250, 0),
    (_ten_k_mda(part_ii_items_7_and_8=_Section("C" * 250), **{"Item 7": _Section("I" * 250)}), {}, "C" * 250, 0),
    (_ten_k_mda(**{"Item 7": _Section("I" * 250)}, mda=_Section("N" * 250)), {}, "I" * 250, 0),
    (_ten_k_mda(mda=_Section("N" * 250)), {}, "N" * 250, 0),
    # A present "Item 7" key wins even as a stub, as in TenK; the stub is then dropped, not replaced.
    (_ten_k_mda(**{"Item 7": _Section("short")}, mda=_Section("N" * 250)), {}, None, 0),
    (_ten_k_mda(), {"7": "<p>" + "Cross reference MD&amp;A. " * 20 + "</p><p>PART III</p>"},
     ("Cross reference MD&A. " * 20).strip(), 1),
    (_ten_k_mda(), {}, None, 1),
], ids=["part-key", "blank-part-key-then-combined", "combined-before-item-key", "item-key-before-friendly",
        "friendly-name", "item-key-stub-stops-the-lookup", "cross-reference-index", "nothing"])
async def test_x0_2_ten_k_lookup_order_is_tenk_getitem(parser, sections, index_items, mda, index_built):
    """X0.2 — a 10-K item resolves the way ``TenK.__getitem__`` resolves it: the canonical part key
    with real text, a combined-items heading, the "Item X" key, the friendly name, then the Cross
    Reference Index, which is built at most once and only when a lookup gets that far."""
    parser.sections, parser.index_items = sections, index_items

    result = await EdgarXBRLService().get_filing_sections(ACC, "10-K", html=HTML)

    assert result.get("mda") == mda
    assert result["risk"] == "r" * 250 and result["financials"] == "f" * 250
    assert parser.index_built == index_built


@pytest.mark.asyncio
@pytest.mark.parametrize(("filing_type", "expected"), [
    ("10-K", {"mda": ("Cross reference MD&A. " * 20).strip()}),  # TenK still reads the index
    ("10-Q", None),
    ("20-F", None),
])
async def test_x0_2_parser_failure_is_a_missing_section(parser, caplog, filing_type, expected):
    """X0.2 — an unparsable document is not an error: a 10-Q or 20-F has no sections and says why,
    and a 10-K still tries the Cross Reference Index, as ``TenK.document`` does when its parser fails
    (it found MD&A there, so nothing is logged)."""
    parser.error = RuntimeError("parser failed")
    parser.index_items = {"7": "<p>" + "Cross reference MD&amp;A. " * 20 + "</p>"}
    caplog.set_level("WARNING")

    assert await EdgarXBRLService().get_filing_sections(ACC, filing_type, html=HTML) == expected
    # All three 10-K items reach the index, which is still built only once.
    assert parser.index_built == (1 if filing_type == "10-K" else 0)
    assert [r.getMessage() for r in caplog.records if r.levelname == "WARNING"] == (
        [] if expected else [f"Section parse found nothing in a {filing_type} document: RuntimeError('parser failed')"])


@pytest.mark.asyncio
@pytest.mark.parametrize(("sections", "error", "warning"), [
    ({"part_i_item_1a": _UnreadableSection(), "part_ii_item_7": _UnreadableSection()}, None,
     "AttributeError(\"'NoneType' object has no attribute 'download'\")"),  # the first error, once
    ({}, RuntimeError("parser failed"), "RuntimeError('parser failed')"),
    ({"part_i_item_1a": _Section("short")}, None, None),  # nothing usable, nothing failed: quiet
], ids=["unreadable-items", "parser-failed-no-index", "empty-parse"])
async def test_x0_2_a_ten_k_read_error_that_leaves_no_section_is_logged(parser, caplog, sections, error, warning):
    """X0.2 — the 10-K's per-item and parser errors are contained, but when they leave no section the
    first one is logged, never swallowed (the silent 2026-10 failure, #1350's rule)."""
    parser.sections, parser.error = sections, error
    caplog.set_level("WARNING")

    assert await EdgarXBRLService().get_filing_sections(ACC, "10-K", html=HTML) is None
    assert [r.getMessage() for r in caplog.records if r.levelname == "WARNING"] == (
        [f"Section parse found nothing in a 10-K document: {warning}"] if warning else [])


@pytest.mark.asyncio
@pytest.mark.parametrize("filing_type", ["8-K", "6-K", "40-F", "DEF 14A", ""])
async def test_x0_2_filing_sections_form_gate(executor_waits, parser, filing_type):
    """X0.2 — only 10-K/10-Q/20-F (amendments normalized) reach the executor; any other form is None
    with no parse and no wait."""
    parser.sections = SECTIONS_10K

    assert await EdgarXBRLService().get_filing_sections(ACC, filing_type, html=HTML) is None
    assert executor_waits == [] and parser.seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("html", ["", None])
async def test_x0_2_no_document_is_none_without_a_parse(executor_waits, parser, html):
    parser.sections = SECTIONS_10K

    assert await EdgarXBRLService().get_filing_sections(ACC, "10-K", html=html) is None
    assert executor_waits == [] and parser.seen == []


@pytest.mark.asyncio
async def test_x0_2_document_over_the_size_cap_is_not_parsed(monkeypatch, parser):
    from app.services.edgar import xbrl_sections

    parser.sections = SECTIONS_10K
    monkeypatch.setattr(xbrl_sections, "_MAX_SECTION_HTML_CHARS", len(HTML) - 1)

    assert await EdgarXBRLService().get_filing_sections(ACC, "10-K", html=HTML) is None
    assert parser.seen == []


@pytest.mark.asyncio
async def test_x0_2_timeout_and_failure_are_logged_and_none(monkeypatch, parser, caplog):
    """X0.2 — the executor's timeout and any other failure are contained: None, with the warning."""
    real_wait_for = asyncio.wait_for

    async def expire(aw, timeout=None):
        if getattr(getattr(aw, "cr_code", None), "co_name", None) == "run_executor_work":
            aw.close()
            raise asyncio.TimeoutError
        return await real_wait_for(aw, timeout)

    caplog.set_level("WARNING")
    with monkeypatch.context() as patch_:
        patch_.setattr(asyncio, "wait_for", expire)
        assert await EdgarXBRLService().get_filing_sections(ACC, "10-K", html=HTML) is None
    parser.sections = _RaisingSections()
    assert await EdgarXBRLService().get_filing_sections(ACC, "10-Q", html=HTML) is None
    messages = [record.getMessage() for record in caplog.records]
    assert f"Section parse timed out for {ACC} after 30s" in messages
    assert f"Section parse failed for {ACC}: sections exploded" in messages


@pytest.mark.asyncio
async def test_x0_2_parses_run_one_at_a_time_and_a_cancelled_queued_parse_never_runs(monkeypatch):
    """X0.2 — parses share one worker, off the SEC pool: a second parse waits for the first, and a
    parse whose waiter is cancelled while it is still queued never runs."""
    started, release, first_running = [], threading.Event(), threading.Event()

    def parse(html, base_form):
        started.append(html)
        first_running.set()
        assert release.wait(5), "test did not release its controlled parse"
        return {"mda": html}

    monkeypatch.setattr(xbrl_service, "_sections_from_html", parse)
    service = EdgarXBRLService()
    first = asyncio.create_task(service.get_filing_sections(ACC, "10-K", html="first"))
    try:
        assert await asyncio.to_thread(first_running.wait, 2)
        second = asyncio.create_task(service.get_filing_sections(ACC, "10-K", html="second"))
        third = asyncio.create_task(service.get_filing_sections(ACC, "10-K", html="third"))
        await asyncio.sleep(0.2)
        assert started == ["first"], "a second parse ran beside the first"
        third.cancel()
        await asyncio.gather(third, return_exceptions=True)
        release.set()
        assert (await first, await second) == ({"mda": "first"}, {"mda": "second"})
        assert started == ["first", "second"], "a cancelled queued parse still ran"
    finally:
        release.set()


# ---------------------------------------------------------------------------
# X0.3 — segment wiring inside the filing-instance extractor (X4), _extract_segments un-stubbed
# ---------------------------------------------------------------------------

def _segment_rows(consolidated_current, consolidated_prior):
    return {
        "us-gaap:Revenues": [
            _fact(CUR, consolidated_current), _fact(PRI, consolidated_prior),
            _segment_fact("Devices", CUR, 400.0), _segment_fact("Devices", PRI, 300.0),
            _segment_fact("Cloud", CUR, 600.0), _segment_fact("Cloud", PRI, 350.0),
        ],
        "us-gaap:OperatingIncomeLoss": [_segment_fact("Devices", CUR, 80.0), _segment_fact("Cloud", CUR, 250.0)],
    }


SEGMENTS = [  # ordered by current revenue, descending (the filer tagged Devices first)
    {"name": "Cloud", "revenue": 600.0, "revenue_prior": 350.0, "operating_income": 250.0,
     "period": POR, "currency": "USD"},
    {"name": "Devices", "revenue": 400.0, "revenue_prior": 300.0, "operating_income": 80.0,
     "period": POR, "currency": "USD"},
]


@pytest.mark.parametrize(("consolidated", "broken", "segments"), [
    ((1000.0, 400.0), (), SEGMENTS),
    ((2500.0, 1000.0), (), "absent"),
    ((1000.0, 400.0), [("us-gaap:Revenues", SEGMENT_AXIS)], "absent"),
], ids=["coherent", "incoherent-with-current-revenue", "segment-failure-contained"])
def test_x0_3_segments_wired_into_instance_extraction(fake_edgar, consolidated, broken, segments):
    """X0.3 — backend/app/services/edgar/xbrl_service.py:508-519 with :238-293 un-stubbed.

    The CURRENT consolidated revenue (``revenue_series[0]``, :511-512) feeds the 0.5-2.0 coherence
    band: 1000 keeps the 1000 segment sum while the prior 400 would drop it, and 2500 drops it while
    the prior 1000 would keep it. An exception is logged and contained (:513-517) and an empty table
    leaves the key absent (:518-519); the extraction itself always completes.
    """
    fake_edgar.filings[ACC] = _Filing("10-K", xb=_XBRL(_segment_rows(*consolidated), broken))

    result = _extract_from_filing_instance_sync(CIK10, ACC)

    assert [point["value"] for point in result["revenue"]] == list(consolidated)
    assert result.get("segments", "absent") == segments


# ---------------------------------------------------------------------------
# X0.4 — dividends component fallback inside the filing-instance extractor (X4)
# ---------------------------------------------------------------------------

def _dividend_rows(total=False):
    rows = {
        "us-gaap:Revenues": [_fact(CUR, 1000.0, currency=None), _fact(PRI, 900.0, currency=None)],
        "us-gaap:PaymentsOfDividendsCommonStock": [_fact(CUR, 300.0), _fact(PRI, 280.0)],
        "us-gaap:PaymentsOfDividendsPreferredStockAndPreferenceStock": [_fact(CUR, 50.0), _fact(PRI, 45.0)],
    }
    if total:
        rows["us-gaap:PaymentsOfDividends"] = [_fact(CUR, 400.0), _fact(PRI, 380.0)]
    return rows


def _paid(period, value, **extra):
    return {"period": period, "value": value, "form": "10-K", "accn": ACC, "currency": "USD", **extra}


@pytest.mark.parametrize(("rows", "broken", "dividends", "currency"), [
    (_dividend_rows(), (), [_paid(CUR[1], 350.0), _paid(PRI[1], 325.0)], "USD"),
    (_dividend_rows(total=True), (),
     [_paid(CUR[1], 400.0, period_start=CUR[0]), _paid(PRI[1], 380.0, period_start=PRI[0])], "USD"),
    (_dividend_rows(), [("us-gaap:PaymentsOfDividendsCommonStock", None)], [], "absent"),
], ids=["components-summed", "total-tag-wins", "fallback-failure-contained"])
def test_x0_4_dividends_component_fallback_in_instance_extraction(fake_edgar, rows, broken, dividends, currency):
    """X0.4 — backend/app/services/edgar/xbrl_service.py:437-452.

    With no total dividends tag (:441) the per-class components are summed per period into entries
    carrying no ``period_start`` and no ``raw_tag`` (:443-449), and their currency votes for the
    reporting currency with weight len(series) (:450; the only currency-bearing facts here). A total
    tag wins through the generic duration path (:415-431). A failure is contained (:451-452).
    """
    fake_edgar.filings[ACC] = _Filing("10-K", xb=_XBRL(rows, broken))

    result = _extract_from_filing_instance_sync(CIK10, ACC)

    assert result["dividends_paid"] == dividends
    assert result.get("reporting_currency", "absent") == currency


# ---------------------------------------------------------------------------
# X0.5 — get_xbrl_data L1 expiry branch (X1 moves the cache to xbrl_cache.py)
# ---------------------------------------------------------------------------

STALE = {"revenue": [{"period": PRI[1], "value": 1.0, "form": "10-K", "accn": "cached"}]}
FRESH = {"revenue": [{"period": POR, "value": 2.0, "form": "10-K", "accn": ACC}]}


@pytest.fixture
def empty_l1():
    """The L1 is process-wide: start and finish empty (public API), so the anchor is order-independent."""
    clear_xbrl_cache()
    yield
    clear_xbrl_cache()


@pytest.mark.asyncio
@pytest.mark.parametrize(("age_hours", "fetched", "served", "deltas", "entries", "awaits"), [
    (23, FRESH, STALE, {"l1_hits": 1, "l1_misses": 0, "l1_evictions": 0}, (1, 1, 0), (0, 0, 0)),
    (25, FRESH, FRESH, {"l1_hits": 0, "l1_misses": 1, "l1_evictions": 0}, (1, 1, 0), (1, 1, 1)),
    (25, None, None, {"l1_hits": 0, "l1_misses": 1, "l1_evictions": 0}, (0, 0, 0), (1, 1, 0)),
], ids=["fresh-hit", "expired-refetch", "expired-no-data"])
async def test_x0_5_get_xbrl_data_l1_expiry_branch(
    empty_l1, monkeypatch, age_hours, fetched, served, deltas, entries, awaits,
):
    """X0.5 — backend/app/services/edgar/xbrl_service.py:688-705 (expiry branch :698-702), read
    through get_xbrl_cache_stats() deltas (:200-235).

    An entry younger than the 24h TTL is served as a hit (:692-697). An expired one is deleted and
    counted as one miss, not an eviction (:698-702), then L2 and the fetch run: a result re-fills L1
    and L2 (:720-724), no data leaves L1 empty and writes nothing (:725-726).
    """
    svc = EdgarXBRLService()
    get_l2, fetch, set_l2 = AsyncMock(return_value=None), AsyncMock(return_value=fetched), AsyncMock(return_value=True)
    monkeypatch.setattr(svc, "_persisted_xbrl", lambda accession_number, cik: None)
    monkeypatch.setattr(svc, "_get_from_redis", get_l2)
    monkeypatch.setattr(svc, "_fetch_xbrl_data", fetch)
    monkeypatch.setattr(svc, "_set_to_redis", set_l2)
    # Rule 7: L1 stamps, expiry, eviction ages and stats all use aware UTC.
    stamped = utcnow() - timedelta(hours=age_hours)
    _cache_set_sync(f"{xbrl_service._XBRL_CACHE_VERSION}:{CIK}:{ACC}", (stamped, STALE))
    before = get_xbrl_cache_stats()

    assert await svc.get_xbrl_data(ACC, CIK) == served

    after = get_xbrl_cache_stats()
    assert all(stamp.utcoffset() == timedelta(0) for stamp, _ in xbrl_service._xbrl_cache.values())
    assert {key: after[key] - before[key] for key in deltas} == deltas
    assert (after["l1_total_entries"], after["l1_valid_entries"], after["l1_expired_entries"]) == entries
    assert (get_l2.await_count, fetch.await_count, set_l2.await_count) == awaits


# ---------------------------------------------------------------------------
# X0.6 — extract_standardized_metrics label inheritance and pass-throughs (X3)
# ---------------------------------------------------------------------------

P1, P0, B0 = "2026-03-28", "2025-03-29", "2025-09-27"  # quarter, prior-year quarter, prior FY-end instant


def _pt(period, value, **extra):
    return {"period": period, "value": value, "form": "10-Q", **extra}


def _labelled_quarter():
    return {
        "revenue": [_pt(P1, 1000.0, fiscal_year=2026, fiscal_period="Q2"),
                    _pt(P0, 900.0, fiscal_year=2025, fiscal_period="Q2")],
        "net_income": [_pt(P1, 100.0), _pt(P0, 81.0, fiscal_year=2025, fiscal_period="Q3")],  # own label
        "gross_profit": [_pt(P1, 400.0), _pt(P0, 350.0)],
        "operating_income": [_pt(P1, 200.0), _pt(P0, 180.0)],
        "operating_cash_flow": [_pt(P1, 150.0), _pt(P0, 120.0)],
        "capital_expenditures": [_pt(P1, 30.0), _pt(P0, 25.0)],
        "total_assets": [_pt(P1, 2000.0), _pt(B0, 1900.0)],
        "shareholders_equity": [_pt(P1, 500.0), _pt(B0, 480.0)],
        "current_assets": [_pt(P1, 600.0), _pt(B0, 550.0)],
        "current_liabilities": [_pt(P1, 300.0), _pt(B0, 275.0)],
        "reporting_currency": "USD",  # non-dict entries the label loop must skip
        "segments": [{"name": "Cloud", "revenue": 600.0, "period": P1, "currency": "USD"}],
    }


def test_x0_6_standardized_label_inheritance():
    """X0.6 — backend/app/services/edgar/xbrl_service.py:1294-1305.

    Labels are collected from every series point that has one, a later metric overwriting an
    earlier one for the same period (:1295-1300; net_income's P0 label beats revenue's), then copied
    onto every series point without its own label, derived ratios/flows included (:1301-1305). A
    point's own label is never overwritten; a period nobody labels stays unlabelled; current/prior
    are the series points, so they carry the inherited label too.
    """
    metrics = EdgarXBRLService().extract_standardized_metrics(_labelled_quarter())

    labels = {
        (key, point["period"]): {k: point[k] for k in ("fiscal_year", "fiscal_period") if k in point}
        for key, entry in metrics.items() if isinstance(entry, dict)
        for point in entry.get("series", [])
    }
    q2_26 = {"fiscal_year": 2026, "fiscal_period": "Q2"}
    q3_25 = {"fiscal_year": 2025, "fiscal_period": "Q3"}
    expected = {("revenue", P1): q2_26, ("revenue", P0): {"fiscal_year": 2025, "fiscal_period": "Q2"},
                ("return_on_equity", P1): q2_26, ("return_on_assets", P1): q2_26}
    for key in ("net_income", "net_margin", "gross_profit", "gross_margin", "operating_income",
                "operating_margin", "operating_cash_flow", "capital_expenditures", "free_cash_flow"):
        expected[(key, P1)], expected[(key, P0)] = q2_26, q3_25
    for key in ("total_assets", "shareholders_equity", "current_assets", "current_liabilities",
                "working_capital", "current_ratio"):
        expected[(key, P1)], expected[(key, B0)] = q2_26, {}
    assert labels == expected
    assert (metrics["net_margin"]["current"]["fiscal_period"], metrics["net_margin"]["prior"]["fiscal_period"]) \
        == ("Q2", "Q3")


_SOURCE = {"accession": ACC, "form": "10-Q", "period_of_report": P1,
           "current": {"period_end": P1, "value": -50.0}, "prior": {"period_end": P0, "value": -40.0}}
_CLASSIFICATION = {"is_financial": False, "sic": "3571", "profile": None, "business_category": None}


@pytest.mark.parametrize(("source", "classification", "passed"), [
    (_SOURCE, _CLASSIFICATION, True),
    ([_SOURCE], "operating", False),
], ids=["dicts-pass-through", "non-dicts-dropped"])
def test_x0_6_standardized_pass_throughs(source, classification, passed):
    """X0.6 — backend/app/services/edgar/xbrl_service.py:1306-1311: ``financing_comparison_source``
    and ``financial_classification`` pass through unchanged when they are dicts, else are absent."""
    data = {"revenue": [_pt(P1, 1000.0)], "financing_comparison_source": source,
            "financial_classification": classification}

    metrics = EdgarXBRLService().extract_standardized_metrics(data)

    expected = {"financing_comparison_source": _SOURCE, "financial_classification": _CLASSIFICATION} if passed else {}
    assert {key: metrics[key] for key in ("financing_comparison_source", "financial_classification")
            if key in metrics} == expected
