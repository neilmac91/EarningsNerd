"""Reported EPS must come from one source-owned, geometrically governed quarter."""
from __future__ import annotations

import gzip
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.edgar.reported_quarterly_eps import (
    extract_reported_quarterly_eps,
    fetch_reported_quarterly_eps,
)
from app.utils.sec_urls import build_sec_archive_url

CIK = "1326801"
ACCESSION = "0001326801-25-000014"
FILENAME = "meta-12312024xexhibit991.htm"
FIXTURES = Path(__file__).parents[1] / "fixtures" / "reported_quarterly_eps"


@pytest.mark.parametrize("year,basic,diluted", [(2023, "5.46", "5.33"), (2024, "8.24", "8.02")])
def test_archived_sec_exhibits_supply_actual_quarterly_eps(year, basic, diluted):
    content = gzip.decompress((FIXTURES / f"meta-q4-{year}.html.gz").read_bytes())
    source = json.loads((FIXTURES / f"meta-q4-{year}.json").read_text())
    result = extract_reported_quarterly_eps(
        content, cik=CIK, accession=source["accession_number"], filename=source["filename"],
        period_end=f"{year}-12-31", currency="USD", source=source,
    )
    assert result["values"] == {"eps_basic": Decimal(basic), "eps_diluted": Decimal(diluted)}
    assert result["source_sha256"] == source["sha256"]


def disclosure() -> str:
    # Synthetic geometry control, not an archived SEC document. It intentionally
    # includes annual EPS next to the quarter so a wrong-column selector fails.
    return """<html><body><div>EXAMPLE ISSUER</div>
<div>CONDENSED CONSOLIDATED STATEMENTS OF INCOME</div>
<div>(In millions, except per share amounts)</div><div>(Unaudited)</div>
<table><tr><td></td><td colspan="4">Three Months Ended December 31,</td>
<td colspan="4">Twelve Months Ended December 31,</td></tr>
<tr><td></td><td colspan="2">2024</td><td colspan="2">2023</td>
<td colspan="2">2024</td><td colspan="2">2023</td></tr>
<tr><td>Revenue</td><td>$</td><td>48,385</td><td>$</td><td>40,111</td>
<td>$</td><td>164,501</td><td>$</td><td>134,902</td></tr>
<tr><td>Net income</td><td>$</td><td>20,838</td><td>$</td><td>14,017</td>
<td>$</td><td>62,360</td><td>$</td><td>39,098</td></tr>
<tr><td>Earnings per share:</td><td colspan="8"></td></tr>
<tr><td>Basic</td><td>$</td><td>8.24</td><td>$</td><td>5.46</td>
<td>$</td><td>24.61</td><td>$</td><td>15.19</td></tr>
<tr><td>Diluted</td><td>$</td><td>8.02</td><td>$</td><td>5.33</td>
<td>$</td><td>23.86</td><td>$</td><td>14.87</td></tr>
<tr><td>Weighted-average shares used to compute earnings per share:</td><td colspan="8"></td></tr>
<tr><td>Basic</td><td></td><td>2,529</td><td></td><td>2,566</td>
<td></td><td>2,534</td><td></td><td>2,574</td></tr>
<tr><td>Diluted</td><td></td><td>2,599</td><td></td><td>2,630</td>
<td></td><td>2,614</td><td></td><td>2,629</td></tr></table></body></html>"""


def receipt(content: bytes) -> dict:
    url = build_sec_archive_url(CIK, ACCESSION) + FILENAME
    return {"representation": "httpx_identity_entity_bytes", "cik": CIK,
            "accession_number": ACCESSION.replace("-", ""), "filename": FILENAME,
            "requested_url": url, "final_url": url, "status_code": 200,
            "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def parse(text: str | None = None, **overrides):
    content = (disclosure() if text is None else text).encode()
    kwargs = {"cik": CIK, "accession": ACCESSION, "filename": FILENAME,
              "period_end": "2024-12-31", "currency": "USD", "source": receipt(content)}
    kwargs.update(overrides)
    return extract_reported_quarterly_eps(content, **kwargs)


def test_exact_quarter_uses_reported_eps_and_preserves_source_evidence():
    result = parse()
    assert result["values"] == {"eps_basic": Decimal("8.24"), "eps_diluted": Decimal("8.02")}
    assert result["period_start"] == "2024-10-01"
    assert result["period_end"] == "2024-12-31"
    assert result["unit"] == "USD/shares"
    assert result["raw_tag"] is None
    assert result["source"] == "reported_eps"
    assert result["source_evidence"]["rows"]["eps_diluted"]["lexical"] == "$ 8.02"
    assert "<table>" in result["source_evidence"]["table_html"]
    assert result["source_sha256"] == hashlib.sha256(disclosure().encode()).hexdigest()
    assert result["source_url"] == build_sec_archive_url(CIK, ACCESSION) + FILENAME


@pytest.mark.parametrize(("old", "new"), [
    ("Three Months Ended December 31,", "Twelve Months Ended December 31,"),
    ("Three Months Ended December 31,", "Three Months Ended September 30,"),
    ('colspan="4">Three Months', 'colspan="1">Three Months'),
    ('colspan="2">2024', 'colspan="1">2024'),
    ("Earnings per share:", "Adjusted earnings per share:"),
    ("Earnings per share:", "Earnings per share from continuing operations:"),
    ("Earnings per share:", "Earnings per share for Class A:"),
    ("Net income</td>", "Net income attributable to common stockholders</td>"),
    ("Basic</td><td>$</td><td>8.24", "Class A basic</td><td>$</td><td>8.24"),
    ("Diluted</td><td>$</td><td>8.02", "Diluted (1)</td><td>$</td><td>8.02"),
    ("<td>$</td><td>8.02</td>", "<td>8</td><td>.02</td>"),
    ("<td>8.02</td>", "<td>8 02</td>"),
    ("<td>8.02</td>", "<td>—</td>"),
    ("<td>8.02</td>", "<td>8.02 1</td>"),
    ("CONSOLIDATED STATEMENTS OF INCOME", "NON-GAAP CONSOLIDATED STATEMENTS OF INCOME"),
    ("(In millions, except per share amounts)", "(In millions)"),
])
def test_unsupported_or_ambiguous_source_never_produces_eps(old, new):
    assert parse(disclosure().replace(old, new)) is None


def test_multiple_statements_and_borrowed_headings_abstain():
    assert parse(disclosure().replace("</body>", disclosure() + "</body>")) is None
    assert parse(disclosure().replace("<table>", "<table><tr><td>Other statement</td></tr></table><table>", 1)) is None


@pytest.mark.parametrize("key,value", [("cik", "1"), ("accession_number", "0" * 18),
    ("sha256", "0" * 64), ("bytes", 2), ("status_code", 302),
    ("representation", "decoded_text"), ("final_url", "https://example.test/other")])
def test_source_receipt_binds_entity_accession_bytes_and_url(key, value):
    source = receipt(disclosure().encode())
    source[key] = value
    assert parse(source=source) is None


def test_explicit_reporting_currency_and_complete_date_required():
    assert parse(currency="JPY") is None
    assert parse(period_end="2024-12-28") is None
    assert parse(period_end="bad-date") is None
    assert parse(filename="../other.htm") is None


@pytest.mark.asyncio
async def test_fetch_uses_existing_attachment_transport_once(monkeypatch):
    from app.services.edgar.compat import sec_edgar_service

    content = disclosure().encode()
    fetch = AsyncMock(return_value=(content, receipt(content)))
    monkeypatch.setattr(sec_edgar_service, "get_filing_attachment_bytes", fetch)
    result = await fetch_reported_quarterly_eps(CIK, ACCESSION, FILENAME, "2024-12-31", currency="USD")
    assert result["values"]["eps_diluted"] == Decimal("8.02")
    fetch.assert_awaited_once_with(CIK, ACCESSION, FILENAME, timeout=20.0, max_retries=1)
    fetch.reset_mock()
    with pytest.raises(ValueError):
        await fetch_reported_quarterly_eps(CIK, ACCESSION, FILENAME, "2024-12-28", currency="USD")
    fetch.assert_not_awaited()
