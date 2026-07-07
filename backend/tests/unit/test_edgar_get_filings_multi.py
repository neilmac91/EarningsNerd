"""QW2 (PR#573) — bounded, single-download filings fetch.

These are the anti-regression gates for the mega-filer timeout fix. The root cause was that the
company filings list fanned out to a fresh ``EdgarCompany`` + edgartools ``trigger_full_load=True``
(full lifetime-history download) once PER form type. The fix (``EdgarClient.get_filings_multi``):
  1. constructs ONE EdgarCompany and issues ONE ``get_filings(form=[...], trigger_full_load=False)``
     call — recent submissions window only, all forms at once;
  2. reads the CHEAP ``report_date`` attribute in ``_transform_filing`` instead of the
     ``period_of_report`` property, which lazily downloads the filing SGML (a per-filing sec.gov
     hit — even ``hasattr`` triggers it).

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


class _FakeEdgarCompany:
    """Records the single get_filings call so tests can assert on it."""

    last_call = None
    construct_count = 0
    cik = 895421

    def __init__(self, ident):
        _FakeEdgarCompany.construct_count += 1
        self.ident = ident

    def get_filings(self, form=None, amendments=None, trigger_full_load=None):
        _FakeEdgarCompany.last_call = {
            "form": form,
            "amendments": amendments,
            "trigger_full_load": trigger_full_load,
        }
        return [
            _FakeEntityFiling("10-K", date(2026, 2, 19), "2025-12-31", "0000895421-26-000010"),
            _FakeEntityFiling("10-Q", date(2026, 5, 5), "2026-03-31", "0000895421-26-000044"),
        ]


@pytest.fixture(autouse=True)
def _patch_edgar_company(monkeypatch):
    _FakeEdgarCompany.last_call = None
    _FakeEdgarCompany.construct_count = 0
    monkeypatch.setattr(client_mod, "EdgarCompany", _FakeEdgarCompany)
    yield


@pytest.mark.asyncio
async def test_multi_issues_one_bounded_call_for_all_forms():
    c = EdgarClient()
    result = await c.get_filings_multi(
        "0000895421",
        [FilingType.FORM_10K, FilingType.FORM_10Q, FilingType.FORM_20F],
        limit=None,
        include_amended=False,
    )

    # Exactly one EdgarCompany constructed for the whole request (not one per form).
    assert _FakeEdgarCompany.construct_count == 1
    call = _FakeEdgarCompany.last_call
    assert call is not None
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
    assert _FakeEdgarCompany.last_call["amendments"] is True
    # Base form only — edgartools expands to include /A when amendments=True.
    assert _FakeEdgarCompany.last_call["form"] == ["10-K"]


@pytest.mark.asyncio
async def test_amended_filing_type_is_normalized_to_base_form():
    c = EdgarClient()
    # Passing an already-amended member must not leak an explicit "/A" string into the filter
    # (that would be stripped by edgartools' amendments=False path and silently drop the form).
    await c.get_filings_multi(
        "0000895421", [FilingType.FORM_10K, FilingType.FORM_10K_AMENDED], include_amended=False
    )
    assert _FakeEdgarCompany.last_call["form"] == ["10-K"]  # de-duped to the base form


@pytest.mark.asyncio
async def test_single_form_get_filings_delegates_to_multi():
    c = EdgarClient()
    result = await c.get_filings("0000895421", FilingType.FORM_10K, limit=1, include_amended=False)
    # Still one EdgarCompany, bounded fetch, and the transform never touched period_of_report.
    assert _FakeEdgarCompany.construct_count == 1
    assert _FakeEdgarCompany.last_call["trigger_full_load"] is False
    assert len(result) == 1  # limit honored


@pytest.mark.asyncio
async def test_empty_form_list_short_circuits_without_fetch():
    c = EdgarClient()
    result = await c.get_filings_multi("0000895421", [], include_amended=False)
    assert result == []
    assert _FakeEdgarCompany.construct_count == 0  # no SEC round-trip at all
