"""Edgartools 5.62.0 retains section content through its element-wise fallback.

The existing summary parity and Outlook tests guard the measured representation.
This gate additionally covers #1063's actual lost affixes and three table seams.
"""
import gzip
from pathlib import Path

from edgar._filings import Filing
from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor

import app.services.edgar  # noqa: F401 — installs the compatibility hook
from app.services.edgar.edgartools_compat import apply_edgartools_backports


def test_homepage_url_points_inside_the_accession_folder():
    filing = Filing(cik=1045609, company="PROLOGIS, INC.", form="10-K",
                    filing_date="2026-02-13", accession_no="0001193125-26-051453")
    expected = "https://www.sec.gov/Archives/edgar/data/1045609/000119312526051453/0001193125-26-051453-index.html"
    assert filing.homepage_url == expected
    assert filing.url == expected


def test_section_compatibility_is_idempotent():
    original = SECSectionExtractor._render_table
    apply_edgartools_backports()
    assert SECSectionExtractor._render_table is original


def test_ford_table_affixes_and_prose_boundaries_survive():
    path = Path(__file__).parents[1] / "fixtures/outlook/ford-2026q1.html.gz"
    document = HTMLParser(ParserConfig(form="10-Q")).parse(gzip.decompress(path.read_bytes()))
    mda = document.sections.get("part_i_item_2").text()
    financials = document.sections.get("part_i_item_1").text()
    assert "ROIC (a)8.6%(12.5%)" in mda
    assert "Adjusted ROIC (Non-GAAP) (b)10.9%12.6%" in mda
    assert "with the SEC.\n\n2026 Guidance" in mda
    assert "(in millions):\n\nFirst Quarter 2025" in financials
    assert "were as follows (in millions):\n\nDecember 31, 2025" in financials
