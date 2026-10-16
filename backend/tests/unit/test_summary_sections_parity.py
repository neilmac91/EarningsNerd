"""The summary's native sections reproduce the excerpts the eval baseline was built on (E28).

From about 2026-10-06 until #1350's backport, the section source (then edgartools' ``Filing.obj()``)
returned nothing and every 10-K, 10-Q and 20-F excerpt was the regex fallback. E28 then moved it to
the primary document the pipeline already fetched (``app/services/edgar/xbrl_sections.py``). These cases run three real filings, already in the
fixtures for other tests, through the production seam and the excerpt assembler. Each excerpt must
match, by sha256 and per-section length, what CI's ``eval-baseline`` recorded for the same filing
while the native path still worked (``coverage_inventory`` of runs 37152414706 and 37191767215,
2026-10-03 and 2026-10-04; ``tasks/review-evidence/e28-native-sections-2026-10-15/``).

It is also the free first check on an edgartools bump: a new parser that changes these three
filings' section text changes the model's input, and the excerpt hash here fails. It reaches only the
routes these filings take (10-K part keys, 10-Q part keys, a 20-F's Item 8 financials); the golden
set's check is a dispatched ``eval-baseline`` and its native-section share. Measure a change per
``backend/evals/RUNBOOK.md`` before re-pinning these values; never re-pin to make a bump pass.

The fixtures are the SEC documents as served, except that SEC appends a bot-detection script tag
with a random path to every response; it falls outside every section and does not reach the
excerpt. No network.
"""
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pytest

from app.services.edgar.compat import xbrl_service
from app.services.openai_service import openai_service

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# (fixture, form, accession, excerpt sha256 and length, supplied section lengths) as recorded.
CASES = [
    ("tax_rate_comparison/figs-20260630.html.gz", "10-Q", "0001628280-26-054342",
     "7e6c85de3f4e88d5d3266827b2d2b570b90dbac642699e34ba400a143d34398e", 112432,
     {"financials": 44455, "mda": 42767, "risk": 210468}),
    ("operating_pretax/meli-2025.html.gz", "10-K", "0001099590-26-000006",
     "f426e9f88ea6b0597d42b9b6ee5dd4bdb560298c1ea994317d34f620c76b98f0", 230682,
     {"financials": 341, "mda": 98636, "risk": 131636}),
    ("operating_pretax/se-2025.html.gz", "20-F", "0001140361-26-015366",
     "7694e07c35a5e69018f99d38ba5f3bde095cf96addf6d2e6d9ea177e0521d84d", 109573,
     {"financials": 9353, "mda": 93170, "risk": 222751}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("fixture", "form", "accession", "sha256", "chars", "supplied"), CASES,
                         ids=[case[1] for case in CASES])
async def test_native_sections_reproduce_the_baseline_excerpt(fixture, form, accession, sha256, chars, supplied):
    # The pipeline hands the seam httpx's decoded ``response.text``; these documents are UTF-8.
    html = gzip.decompress((FIXTURES / fixture).read_bytes()).decode("utf-8")

    sections = await xbrl_service.get_filing_sections(accession, form, html=html)
    excerpt = openai_service.assemble_excerpt_from_sections(sections, form, filing_text=html)

    assert {key: len(text) for key, text in (sections or {}).items()} == supplied, (
        f"{form} {accession}: the parsed sections no longer match the baseline's (E28 parity). If an "
        "edgartools change caused this, it changes model input: measure it per backend/evals/RUNBOOK.md."
    )
    assert (hashlib.sha256(excerpt.encode("utf-8")).hexdigest(), len(excerpt)) == (sha256, chars), (
        f"{form} {accession}: the native excerpt differs from the one the eval baseline was built on."
    )
