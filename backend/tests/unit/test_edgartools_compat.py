"""The edgartools homepage backport (app/services/edgar/edgartools_compat.py).

SEC answers the short filing-index URL ``/Archives/edgar/data/<cik>/<accession>-index.html`` with
403 "Access Denied"; the index page inside the accession folder still answers. The pinned edgartools
5.58.0 builds the short URL, and ``Filing.html()`` reads an inline-XBRL primary document through it,
so every 10-K/10-Q/20-F section read failed until the backport. No test here touches the network.
"""
from types import SimpleNamespace

import pytest
from edgar._filings import Filing, FilingHomepage

import app.services.edgar  # noqa: F401 — importing the edgar package applies the backports
from app.services.edgar.edgartools_compat import (
    ORIGINAL_HOMEPAGE_URL,
    _builds_in_folder_url,
    backport_homepage_url,
)

CIK, ACCESSION = 1045609, "0001193125-26-051453"
IN_FOLDER = "https://www.sec.gov/Archives/edgar/data/1045609/000119312526051453/0001193125-26-051453-index.html"


def _filing() -> Filing:
    return Filing(cik=CIK, company="PROLOGIS, INC.", form="10-K", filing_date="2026-02-13", accession_no=ACCESSION)


def test_homepage_url_points_inside_the_accession_folder():
    filing = _filing()
    assert filing.homepage_url == IN_FOLDER
    assert filing.url == IN_FOLDER


def test_the_backport_is_idempotent(monkeypatch):
    # Restore the class attribute afterwards, so a failure here cannot patch Filing for later tests.
    monkeypatch.setattr(Filing, "homepage_url", Filing.homepage_url)
    assert backport_homepage_url() is False
    assert _filing().homepage_url == IN_FOLDER


def test_the_pinned_release_still_needs_the_backport():
    if _builds_in_folder_url(ORIGINAL_HOMEPAGE_URL):
        pytest.fail(
            "edgartools now builds the in-folder index URL itself (upstream 5.61.0, GH #1421): delete "
            "backport_homepage_url, its call in apply_edgartools_backports and this test"
        )


def test_html_of_an_inline_xbrl_filing_reads_the_in_folder_homepage(monkeypatch, request):
    """The path that broke: an inline-XBRL document starts with an XML prolog, so Filing.html()
    re-reads it through the homepage instead of returning the SGML copy."""
    # Filing.html is lru_cached per accession process-wide: start and end with it empty.
    Filing.html.cache_clear()
    request.addfinalizer(Filing.html.cache_clear)
    ixbrl = "<?xml version='1.0' encoding='ASCII'?>\n<html><body><p>Item 1A. Risk Factors</p></body></html>"
    document = "<html><body><p>Item 1A. Risk Factors</p></body></html>"
    requested: list[str] = []
    monkeypatch.setattr(Filing, "sgml", lambda self: SimpleNamespace(html=lambda: ixbrl))

    def load(url):
        requested.append(url)
        return SimpleNamespace(primary_html_document=SimpleNamespace(download=lambda: document))

    monkeypatch.setattr(FilingHomepage, "load", staticmethod(load))

    assert _filing().html() == document
    assert requested == [IN_FOLDER]
