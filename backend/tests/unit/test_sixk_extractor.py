"""Phase 4: 6-K exhibit grounding-text extraction (no network — edgartools fully mocked).

Covers the earnings-release path, the fallback to full exhibit text, defensive handling of a
raising attribute (edgartools version drift / edge case #844 must never propagate), and the
empty-filing → None case.
"""
from app.services.edgar import sixk_extractor as sx


class _FakePR:
    def __init__(self, text):
        self._t = text

    def text(self):
        return self._t


class _FakePRs:
    def __init__(self, texts):
        self._prs = [_FakePR(t) for t in texts]

    def __len__(self):
        return len(self._prs)

    def __getitem__(self, i):
        return self._prs[i]


class _FakeSixK:
    def __init__(self, *, content_description=None, report_month=None, press=None, full_text=None):
        self.content_description = content_description
        self.report_month = report_month
        self._press = _FakePRs(press) if press is not None else None
        self._full_text = full_text

    @property
    def press_releases(self):
        return self._press

    def text(self):
        return self._full_text


class _RaisingPressSixK(_FakeSixK):
    @property
    def press_releases(self):  # simulates the edgartools edge case where access raises
        raise RuntimeError("edgartools #844")


class _FakeFiling:
    def __init__(self, obj):
        self._obj = obj

    def obj(self):
        return self._obj


class _FakeCompany:
    def __init__(self, filings):
        self._filings = filings

    def get_filings(self, accession_number=None, trigger_full_load=None):
        return self._filings


def _patch(monkeypatch, six_k, *, filings=None):
    flist = filings if filings is not None else [_FakeFiling(six_k)]
    company = _FakeCompany(flist)
    monkeypatch.setattr(
        sx, "resolve_filing_by_accession", lambda cik, accession_number: (company, flist)
    )


def test_earnings_release_text_with_cover_header(monkeypatch):
    six_k = _FakeSixK(
        content_description="Press release announcing first-half results",
        report_month="September 2025",
        press=["Revenue rose to RMB 247.5 billion for the six months ended 30 September 2025."],
        full_text="FULL EXHIBIT DUMP (should be ignored when a press release exists)",
    )
    _patch(monkeypatch, six_k)

    out = sx._extract_sixk_text_sync("0001577552", "acc-1")
    assert out is not None
    assert "RMB 247.5 billion" in out               # press-release body
    assert "first-half results" in out               # cover content_description header
    assert "September 2025" in out                    # reporting month header
    assert "FULL EXHIBIT DUMP" not in out             # press release preferred over .text()


def test_falls_back_to_full_text_when_no_press_release(monkeypatch):
    six_k = _FakeSixK(press=None, full_text="Interim condensed statements, profit €1.9B.")
    _patch(monkeypatch, six_k)
    out = sx._extract_sixk_text_sync("0000000001", "acc-2")
    assert out == "Interim condensed statements, profit €1.9B."


def test_raising_press_releases_is_defensive(monkeypatch):
    # A property that raises must not propagate — fall back to .text(), never crash.
    six_k = _RaisingPressSixK(full_text="Board appointed a new CFO. No financial results.")
    _patch(monkeypatch, six_k)
    out = sx._extract_sixk_text_sync("0000000002", "acc-3")
    assert out == "Board appointed a new CFO. No financial results."


def test_cover_metadata_only_when_no_body(monkeypatch):
    six_k = _FakeSixK(content_description="Notice of annual general meeting", press=None, full_text=None)
    _patch(monkeypatch, six_k)
    out = sx._extract_sixk_text_sync("0000000003", "acc-4")
    assert out is not None
    assert "annual general meeting" in out


def test_empty_filing_returns_none(monkeypatch):
    six_k = _FakeSixK(press=None, full_text=None)
    _patch(monkeypatch, six_k)
    assert sx._extract_sixk_text_sync("0000000004", "acc-5") is None


def test_no_filing_resolved_returns_none(monkeypatch):
    _patch(monkeypatch, None, filings=[])
    assert sx._extract_sixk_text_sync("0000000005", "acc-6") is None


def test_text_capped(monkeypatch):
    six_k = _FakeSixK(press=["X" * (sx._SIXK_TEXT_CAP + 5000)])
    _patch(monkeypatch, six_k)
    out = sx._extract_sixk_text_sync("0000000006", "acc-7")
    assert out is not None and len(out) <= sx._SIXK_TEXT_CAP
