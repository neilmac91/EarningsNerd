"""QW2 (PR#573) — bounded, single-download filings fetch.

These are the anti-regression gates for the mega-filer timeout fix. The root cause was that the
company filings list fanned out to a fresh ``EdgarCompany`` + edgartools ``trigger_full_load=True``
(full lifetime-history download) once PER form type. The fix (``EdgarClient.get_filings_multi``):
  1. constructs ONE EdgarCompany and issues ONE ``get_filings(form=[...], trigger_full_load=False)``
     call — recent submissions window only, all forms at once;
  2. reads the CHEAP ``report_date`` attribute in ``_transform_filing`` instead of the
     ``period_of_report`` property, which lazily downloads the filing SGML (a per-filing sec.gov
     hit — even ``hasattr`` triggers it);
  3. for BOUNDED single-latest callers only (limit set: precompute / get_latest_filing), falls back
     to a full-history fetch when the recent window under-delivers — the unbounded LIST path
     (limit=None) never full-loads.

No network: ``EdgarCompany`` is faked. A fake filing whose ``period_of_report`` RAISES proves the
transform never touches it.
"""
from datetime import date

import pytest

from app.services.edgar import client as client_mod
from app.services.edgar.client import EdgarClient
from app.services.edgar.config import FilingType


class _FakeEntityFiling:
    """Mimics edgartools' EntityFiling: cheap metadata attrs only. ``period_of_report`` is a
    booby-trap — accessing it (the old code did, via hasattr) must fail the test."""

    def __init__(self, form, filing_date, report_date, accession, primary_document="primary.htm"):
        self.form = form
        self.filing_date = filing_date
        self.report_date = report_date
        self.accession_number = accession
        self.primary_document = primary_document
        self.company = "Test Co"
        self.cik = 895421

    @property
    def period_of_report(self):  # pragma: no cover - must never be reached
        raise AssertionError(
            "period_of_report was accessed — it triggers a live SGML download; use report_date"
        )


def _sample_filings():
    return [
        _FakeEntityFiling("10-K", date(2026, 2, 19), "2025-12-31", "0000895421-26-000010"),
        _FakeEntityFiling("10-Q", date(2026, 5, 5), "2026-03-31", "0000895421-26-000044"),
    ]


class _FakeEdgarCompany:
    """Records every get_filings call; returns a configurable recent-window vs full-load result."""

    calls = []
    construct_count = 0
    recent_result = None   # set per test; defaults to sample in fixture
    full_result = None
    cik = 895421

    def __init__(self, ident):
        _FakeEdgarCompany.construct_count += 1
        self.ident = ident

    def get_filings(self, form=None, amendments=None, trigger_full_load=None, sort_by=None):
        _FakeEdgarCompany.calls.append(
            {
                "form": form,
                "amendments": amendments,
                "trigger_full_load": trigger_full_load,
                "sort_by": sort_by,
            }
        )
        return _FakeEdgarCompany.full_result if trigger_full_load else _FakeEdgarCompany.recent_result

    @classmethod
    def last_call(cls):
        return cls.calls[-1]


@pytest.fixture(autouse=True)
def _patch_edgar_company(monkeypatch):
    _FakeEdgarCompany.calls = []
    _FakeEdgarCompany.construct_count = 0
    _FakeEdgarCompany.recent_result = _sample_filings()
    _FakeEdgarCompany.full_result = _sample_filings()
    client_mod._empty_fallback_cache.clear()
    monkeypatch.setattr(client_mod, "EdgarCompany", _FakeEdgarCompany)
    yield
    client_mod._empty_fallback_cache.clear()


@pytest.mark.asyncio
async def test_multi_issues_one_bounded_call_for_all_forms():
    c = EdgarClient()
    result = await c.get_filings_multi(
        "0000895421",
        [FilingType.FORM_10K, FilingType.FORM_10Q, FilingType.FORM_20F],
        limit=None,
        include_amended=False,
    )

    # Exactly one EdgarCompany constructed and exactly one get_filings call for the whole request.
    assert _FakeEdgarCompany.construct_count == 1
    assert len(_FakeEdgarCompany.calls) == 1
    call = _FakeEdgarCompany.last_call()
    # The download-everything default is explicitly disabled — recent window only.
    assert call["trigger_full_load"] is False
    # All requested BASE forms passed in a single call, order-stable; no "/A" strings.
    assert call["form"] == ["10-K", "10-Q", "20-F"]
    assert all("/A" not in f for f in call["form"])
    # amendments flag mirrors include_amended (False → base forms only).
    assert call["amendments"] is False
    # Transformed rows carry the period-end from the cheap report_date field.
    assert len(result) == 2
    by_type = {f.filing_type: f for f in result}
    assert by_type[FilingType.FORM_10K].period_end_date == date(2025, 12, 31)
    assert by_type[FilingType.FORM_10Q].period_end_date == date(2026, 3, 31)


@pytest.mark.asyncio
async def test_include_amended_true_passes_amendments_flag():
    c = EdgarClient()
    await c.get_filings_multi("0000895421", [FilingType.FORM_10K], include_amended=True)
    assert _FakeEdgarCompany.last_call()["amendments"] is True
    # Base form only — edgartools expands to include /A when amendments=True.
    assert _FakeEdgarCompany.last_call()["form"] == ["10-K"]


@pytest.mark.asyncio
async def test_amended_filing_type_forces_amendments_on_without_leaking_slash_a():
    c = EdgarClient()
    # An explicitly-amended request must not silently collapse to non-amended base rows: the form
    # de-dupes to the base string, but amendments is forced True so the /A filings ARE returned.
    await c.get_filings_multi(
        "0000895421", [FilingType.FORM_10K, FilingType.FORM_10K_AMENDED], include_amended=False
    )
    call = _FakeEdgarCompany.last_call()
    assert call["form"] == ["10-K"]  # de-duped to the base form, no "/A" string
    assert call["amendments"] is True  # forced on because an amended form was requested


@pytest.mark.asyncio
async def test_single_form_get_filings_delegates_to_multi():
    c = EdgarClient()
    result = await c.get_filings("0000895421", FilingType.FORM_10K, limit=1, include_amended=False)
    # Still one EdgarCompany; recent window had enough rows so no full-load fallback.
    assert _FakeEdgarCompany.construct_count == 1
    assert all(call["trigger_full_load"] is False for call in _FakeEdgarCompany.calls)
    assert len(result) == 1  # limit honored


@pytest.mark.asyncio
async def test_empty_form_list_short_circuits_without_fetch():
    c = EdgarClient()
    result = await c.get_filings_multi("0000895421", [], include_amended=False)
    assert result == []
    assert _FakeEdgarCompany.construct_count == 0  # no SEC round-trip at all


@pytest.mark.asyncio
async def test_bounded_caller_falls_back_to_full_load_when_recent_window_empty():
    # Simulate a filer whose latest 10-K is older than the recent window: recent returns nothing,
    # full history has it. A bounded caller (limit=1: precompute / get_latest_filing) must still find it.
    _FakeEdgarCompany.recent_result = []
    _FakeEdgarCompany.full_result = [
        _FakeEntityFiling("10-K", date(2024, 2, 15), "2023-12-31", "0000895421-24-000009")
    ]

    c = EdgarClient()
    result = await c.get_filings_multi("0000895421", [FilingType.FORM_10K], limit=1)

    # Two fetches: recent (empty) then the full-history fallback.
    assert len(_FakeEdgarCompany.calls) == 2
    assert _FakeEdgarCompany.calls[0]["trigger_full_load"] is False
    assert _FakeEdgarCompany.calls[1]["trigger_full_load"] is True
    # The fallback sorts at the Arrow level so islice(limit) is exact, not shard-order-dependent.
    assert _FakeEdgarCompany.calls[1]["sort_by"] == [("filing_date", "descending")]
    assert len(result) == 1
    assert result[0].period_end_date == date(2023, 12, 31)


@pytest.mark.asyncio
async def test_both_windows_empty_returns_empty_with_exactly_two_calls():
    # Form-mismatched company (e.g. precompute 10-K for a 20-F-only FPI): recent AND full are empty.
    # Must return [] with EXACTLY 2 calls (recent + one fallback, no retry-loop creep).
    _FakeEdgarCompany.recent_result = []
    _FakeEdgarCompany.full_result = []

    c = EdgarClient()
    result = await c.get_filings_multi("0000895421", [FilingType.FORM_10K], limit=1)

    assert result == []
    assert len(_FakeEdgarCompany.calls) == 2
    assert _FakeEdgarCompany.calls[0]["trigger_full_load"] is False
    assert _FakeEdgarCompany.calls[1]["trigger_full_load"] is True


@pytest.mark.asyncio
async def test_get_latest_filing_raises_when_both_windows_empty():
    # precompute's `no_filings` status depends on this surfacing as FilingNotFoundError.
    from app.services.edgar.exceptions import FilingNotFoundError

    _FakeEdgarCompany.recent_result = []
    _FakeEdgarCompany.full_result = []

    c = EdgarClient()
    with pytest.raises(FilingNotFoundError):
        await c.get_latest_filing("0000895421", FilingType.FORM_10K)


@pytest.mark.asyncio
async def test_bounded_caller_does_not_full_load_when_recent_has_any_result():
    # Regression guard: the fallback triggers ONLY on an empty recent window, never merely because
    # len < limit. A bounded caller's default limit is 10 while an annual form yields ~1/year, so a
    # `< limit` trigger would full-load on nearly every call and defeat the recent-window fix.
    _FakeEdgarCompany.recent_result = [
        _FakeEntityFiling("10-K", date(2026, 2, 19), "2025-12-31", "0000895421-26-000010")
    ]
    _FakeEdgarCompany.full_result = _sample_filings()

    c = EdgarClient()
    result = await c.get_filings("0000895421", FilingType.FORM_10K, limit=10)

    # One filing found in the recent window (< limit=10) — but NO full-load fallback.
    assert len(_FakeEdgarCompany.calls) == 1
    assert _FakeEdgarCompany.calls[0]["trigger_full_load"] is False
    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_path_never_full_loads_even_when_recent_empty():
    # The unbounded list path (limit=None) must NEVER pay the full-history cost — that is the whole
    # point of QW2. Deep history comes from DB-first serving, not a full-load here.
    _FakeEdgarCompany.recent_result = []
    _FakeEdgarCompany.full_result = _sample_filings()

    c = EdgarClient()
    result = await c.get_filings_multi(
        "0000895421", [FilingType.FORM_10K, FilingType.FORM_10Q], limit=None
    )

    assert result == []
    assert len(_FakeEdgarCompany.calls) == 1
    assert _FakeEdgarCompany.calls[0]["trigger_full_load"] is False


@pytest.mark.asyncio
async def test_negative_cache_skips_repeat_full_load_for_form_mismatched_company():
    # A company that doesn't file the requested form (e.g. precompute 10-K for a 20-F-only FPI):
    # the first bounded call full-loads (recent + full, both empty) and remembers the miss; the
    # second call within the TTL must SKIP the full-load entirely (recent only), sparing the
    # recurring 43-shard download + breaker pressure.
    _FakeEdgarCompany.recent_result = []
    _FakeEdgarCompany.full_result = []

    c = EdgarClient()
    first = await c.get_filings_multi("0000895421", [FilingType.FORM_10K], limit=1)
    assert first == []
    assert [call["trigger_full_load"] for call in _FakeEdgarCompany.calls] == [False, True]

    _FakeEdgarCompany.calls = []  # reset call log for the second call
    second = await c.get_filings_multi("0000895421", [FilingType.FORM_10K], limit=1)
    assert second == []
    # Recent window only — no full-load this time (negative cache hit).
    assert [call["trigger_full_load"] for call in _FakeEdgarCompany.calls] == [False]


@pytest.mark.asyncio
async def test_negative_cache_expires_after_ttl(monkeypatch):
    # After the TTL, a form-mismatched company is re-checked (a company that later starts filing the
    # form must not be negatively cached forever).
    from datetime import timedelta

    _FakeEdgarCompany.recent_result = []
    _FakeEdgarCompany.full_result = []

    c = EdgarClient()
    await c.get_filings_multi("0000895421", [FilingType.FORM_10K], limit=1)

    # Age the cache entry past its TTL.
    key = ("0000895421", ("10-K",))
    client_mod._empty_fallback_cache[key] = (
        client_mod._empty_fallback_cache[key] - client_mod._EMPTY_FALLBACK_TTL - timedelta(minutes=1)
    )

    _FakeEdgarCompany.calls = []
    await c.get_filings_multi("0000895421", [FilingType.FORM_10K], limit=1)
    # Stale entry → full-load fallback runs again.
    assert [call["trigger_full_load"] for call in _FakeEdgarCompany.calls] == [False, True]


def test_negative_cache_key_is_form_order_independent():
    # A same-set request in a different form order must be a cache hit, not a miss.
    client_mod._mark_empty_fallback("0000895421", ["10-K", "10-Q"])
    assert client_mod._empty_fallback_fresh("0000895421", ["10-Q", "10-K"]) is True
    # A different set is still a miss.
    assert client_mod._empty_fallback_fresh("0000895421", ["10-K"]) is False


# ---- get_filing_by_accession: recent-first, full-history fallback ----


class _FakeAccessionCompany:
    """Records the trigger_full_load flag of each accession lookup and returns a configurable hit."""

    def __init__(self, recent_hit, full_hit):
        self.recent_hit = recent_hit
        self.full_hit = full_hit
        self.calls = []

    def get_filings(self, accession_number=None, trigger_full_load=None):
        self.calls.append(trigger_full_load)
        return self.full_hit if trigger_full_load else self.recent_hit


def test_get_filing_by_accession_recent_hit_no_full_load():
    from app.services.edgar.client import get_filing_by_accession

    filing = object()
    company = _FakeAccessionCompany(recent_hit=[filing], full_hit=[])
    result = get_filing_by_accession(company, "0000895421-26-000010")

    assert result == [filing]
    assert company.calls == [False]  # recent window only, never full-loaded


def test_get_filing_by_accession_falls_back_to_full_history():
    from app.services.edgar.client import get_filing_by_accession

    filing = object()
    company = _FakeAccessionCompany(recent_hit=[], full_hit=[filing])
    result = get_filing_by_accession(company, "0000895421-16-000009")

    assert result == [filing]
    assert company.calls == [False, True]  # recent miss → full history


def test_get_filing_by_accession_returns_empty_when_absent_everywhere():
    from app.services.edgar.client import get_filing_by_accession

    company = _FakeAccessionCompany(recent_hit=[], full_hit=[])
    result = get_filing_by_accession(company, "9999999999-99-999999")

    assert result == []
    assert company.calls == [False, True]
