"""Offline same-accession Item 2.02 grounding and bounded SEC entity transport."""
import asyncio
import hashlib
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.edgar import compat, eightk_extractor as ex
from app.services.edgar.exceptions import EdgarError
from app.utils.sec_urls import build_sec_archive_url

CIK = "0000872589"
ACCESSION = "0000872589-26-000123"
ARCHIVE = build_sec_archive_url(CIK, ACCESSION)
PRIMARY_URL = ARCHIVE + "current.htm"
RELEASE = b"<html><body><h1>Third quarter results</h1><p>Revenue $5.1 billion. GAAP EPS $19.16.</p></body></html>"


def cover(*links):
    rows = "".join(f'<tr><td><a href="{href}">{label}</a></td><td>Quarterly earnings release</td></tr>' for href, label in links)
    return '<html><body><p>Item 2.02 Results of Operations and Financial Condition.</p><p>The earnings release is attached as Exhibit 99.1.</p><table>' + rows + '</table></body></html>'


def transport(monkeypatch, contents=None):
    contents = contents or [RELEASE]
    async def fetch(cik, accession, filename, **kwargs):
        content = contents[min(fetch.count, len(contents) - 1)]
        fetch.count += 1
        return content, {"filename": filename, "accession_number": accession, "requested_url": ARCHIVE + filename, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    fetch.count = 0
    mock = AsyncMock(side_effect=fetch)
    monkeypatch.setattr(ex.sec_edgar_service, "get_filing_attachment_bytes", mock)
    return mock


@pytest.mark.asyncio
async def test_earnings_cover_includes_exact_attached_release_and_source_hash(monkeypatch):
    fetch = transport(monkeypatch)
    result = await ex.get_eightk_grounding(cover(("release.htm", "99.1"), ("release.htm#results", "99.1")), PRIMARY_URL, CIK, ACCESSION)
    assert "Item 2.02" in result.text
    assert "Revenue $5.1 billion. GAAP EPS $19.16." in result.text
    assert result.provenance["accession_number"] == ACCESSION
    assert result.provenance["members"][0]["sha256"] == hashlib.sha256(RELEASE).hexdigest()
    assert result.provenance["members"][0]["requested_url"] == ARCHIVE + "release.htm"
    fetch.assert_awaited_once_with(CIK, ACCESSION, "release.htm", timeout=20, max_retries=1, max_bytes=compat.MAX_SEC_ATTACHMENT_BYTES)


@pytest.mark.asyncio
@pytest.mark.parametrize("primary", ["<p>Item 5.02 Appointment of director.</p><a href='outside.htm'>99.1</a>", "<p>Item 2.02 Results of Operations. Revenue $5.1 billion disclosed here.</p>"])
async def test_no_advertised_earnings_attachment_preserves_primary(monkeypatch, primary):
    fetch = transport(monkeypatch)
    result = await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert result.text == primary
    assert result.provenance["members"] == []
    fetch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("href", ["https://issuer.example/release.htm", "../000087258926000122/release.htm", "/Archives/edgar/data/872589/000087258926000122/release.htm", "release.htm?redirect=1", "..%2frelease.htm", "https://www.sec.gov.evil.example/release.htm"])
async def test_other_sources_are_rejected_before_any_attachment_request(monkeypatch, href):
    fetch = transport(monkeypatch)
    with pytest.raises(EdgarError) as caught:
        await ex.get_eightk_grounding(cover((href, "99.1")), PRIMARY_URL, CIK, ACCESSION)
    assert caught.value.code == "EDGAR_EARNINGS_EXHIBIT_UNAVAILABLE"
    fetch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("primary,reason", [(cover(), "advertised_exhibit_missing"), (cover(*[(f"release{i}.htm", f"99.{i}") for i in range(1, 5)]), "too_many_exhibits")])
async def test_missing_or_unbounded_advertised_members_fail_closed(monkeypatch, primary, reason):
    fetch = transport(monkeypatch)
    with pytest.raises(EdgarError) as caught:
        await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert caught.value.context["reason"] == reason
    fetch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("content,reason", [(b"<html></html>", "empty_exhibit"), (b"%PDF-1.4", "unsupported_exhibit_format"), (b"<title>Your Request Originates from an Undeclared Automated Tool</title><p>Please declare your traffic by updating your user agent</p>", "sec_automated_tool_block")])
async def test_invalid_200_body_cannot_be_used_as_earnings_grounding(monkeypatch, content, reason):
    transport(monkeypatch, [content])
    with pytest.raises(EdgarError) as caught:
        await ex.get_eightk_grounding(cover(("release.htm", "99.1")), PRIMARY_URL, CIK, ACCESSION)
    assert caught.value.context["reason"] == reason


@pytest.mark.asyncio
async def test_legitimate_filing_quoting_policy_is_not_a_block_page(monkeypatch):
    transport(monkeypatch, [b"<title>Quarterly results</title><p>Please declare your traffic by updating your user agent. Revenue $5.1 billion.</p>"])
    result = await ex.get_eightk_grounding(cover(("release.htm", "99.1")), PRIMARY_URL, CIK, ACCESSION)
    assert "Revenue $5.1 billion" in result.text


@pytest.mark.asyncio
async def test_members_share_one_byte_budget_and_no_silent_text_truncation(monkeypatch):
    fetch = transport(monkeypatch, [RELEASE, RELEASE])
    await ex.get_eightk_grounding(cover(("first.htm", "99.1"), ("second.htm", "99.2")), PRIMARY_URL, CIK, ACCESSION)
    assert [call.kwargs["max_bytes"] for call in fetch.await_args_list] == [compat.MAX_SEC_ATTACHMENT_BYTES, compat.MAX_SEC_ATTACHMENT_BYTES - len(RELEASE)]
    monkeypatch.setattr(ex, "MAX_GROUNDING_CHARACTERS", 10)
    with pytest.raises(EdgarError) as caught:
        await ex.get_eightk_grounding(cover(("release.htm", "99.1")), PRIMARY_URL, CIK, ACCESSION)
    assert caught.value.context["reason"] == "earnings_grounding_too_large"


@pytest.mark.asyncio
async def test_total_deadline_includes_attachment_admission(monkeypatch):
    cancelled = asyncio.Event()
    async def wait_for_token(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    monkeypatch.setattr(ex.sec_edgar_service, "get_filing_attachment_bytes", wait_for_token)
    with pytest.raises(EdgarError) as caught:
        await ex.get_eightk_grounding(cover(("release.htm", "99.1")), PRIMARY_URL, CIK, ACCESSION, timeout=0.05)
    assert caught.value.context["reason"] == "exhibit_deadline"
    assert cancelled.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize("declared", [None, "1", "100"])
async def test_remaining_byte_budget_enforced_on_physical_response(monkeypatch, declared):
    reads = []
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            reads.append(True)
            yield b"a" * 20
    def respond(request):
        return httpx.Response(200, stream=Stream(), headers={} if declared is None else {"content-length": declared})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(compat.httpx, "AsyncClient", lambda: real_client(transport=httpx.MockTransport(respond)))
    async def execute(fn):
        return await fn()
    monkeypatch.setattr(compat.sec_rate_limiter, "execute", execute)
    with pytest.raises(EdgarError, match="10-byte entity limit"):
        await compat.sec_edgar_service.get_filing_attachment_bytes(CIK, ACCESSION, "release.htm", max_bytes=10)
    assert bool(reads) == (declared != "100")


@pytest.mark.asyncio
async def test_ancillary_member_cannot_stand_in_for_missing_advertised_release(monkeypatch):
    fetch = transport(monkeypatch)
    primary = '<p>Item 2.02 Results of Operations. The earnings release is attached as Exhibit 99.1.</p><p>Item 9.01 Exhibits.</p><a href="slides.htm">99.2</a>'
    with pytest.raises(EdgarError) as caught:
        await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert caught.value.context["reason"] == "advertised_exhibit_missing"
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_unrelated_item_does_not_add_an_earnings_exhibit_requirement(monkeypatch):
    fetch = transport(monkeypatch)
    primary = '<p>Item 2.02 Results of Operations. The earnings release is attached as Exhibit 99.1.</p><p>Item 5.02 Compensatory arrangement in Exhibit 99.2, incorporated by reference.</p><p>Item 9.01 Exhibits.</p><a href="release.htm">99.1</a>'
    result = await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert "Revenue $5.1 billion" in result.text
    fetch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("heading", ["Items 2.02 and 9.01", "Items 8.01 and 2.02", "Item <span>2.</span><span>0</span><span>2</span>"])
async def test_combined_and_fragmented_earnings_item_headings_resolve_release(monkeypatch, heading):
    fetch = transport(monkeypatch)
    primary = f'<h2>{heading} Results of Operations</h2><p>Our earnings release is attached as <a href="release.htm">Exhibit 99.1</a>.</p>'
    result = await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert "Revenue $5.1 billion" in result.text
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_hidden_nodes_never_become_visible_sources(monkeypatch):
    fetch = transport(monkeypatch, [RELEASE + b'<div style="display:none">Revenue $90 billion</div><ix:hidden>EPS $90</ix:hidden><template>Cash flow $90 billion</template>'])
    primary = cover(("release.htm", "99.1")) + '<div hidden><a href="poison.htm">Exhibit 99.2</a> Revenue $91 billion</div>'
    result = await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert "Revenue $5.1 billion" in result.text
    assert "$90" not in result.text
    assert "$91" not in result.text
    assert "poison.htm" not in result.text
    fetch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("reference,label", [("99.1", "99.<span>1</span>"), ("99.<span>1</span>", "99.1")])
async def test_fragmented_exhibit_number_matches_advertised_member(monkeypatch, reference, label):
    fetch = transport(monkeypatch)
    primary = f'<p>Item 2.02 Results of Operations. The earnings release is attached as Exhibit {reference}.</p><p>Item 9.01 Exhibits.</p><a href="release.htm">{label}</a>'
    result = await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert "Revenue $5.1 billion" in result.text
    fetch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("block", ["div", "p", "li"])
async def test_leaf_exhibit_entry_associates_sibling_number_with_description_link(monkeypatch, block):
    fetch = transport(monkeypatch)
    primary = (
        '<p>Item 2.02 Results of Operations. The earnings release is furnished as Exhibit 99.1.</p>'
        '<p>Item 9.01 Financial Statements and Exhibits.</p>'
        f'<{block}><span>99.1 </span><span><a href="release.htm">'
        f'Press Release, dated October 30, 2026, Reporting Third Quarter Results.</a></span></{block}>'
    )
    result = await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert "Revenue $5.1 billion" in result.text
    assert [member["filename"] for member in result.provenance["members"]] == ["release.htm"]
    fetch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", [
    '<div><p>99.1</p><a href="unrelated.htm">Press release</a></div>',
    '<div>99.1 <a href="first.htm">Press release</a><a href="second.htm">Other release</a></div>',
    '<div>99.1 and 99.2 <a href="only-one.htm">Press release</a></div>',
    '<div>99.2 <a href="ancillary.htm">Press release</a></div>',
])
async def test_non_table_entries_cannot_resolve_ambiguous_or_missing_advertised_member(monkeypatch, entry):
    fetch = transport(monkeypatch)
    primary = (
        '<p>Item 2.02 Results of Operations. The earnings release is furnished as Exhibit 99.1.</p>'
        '<p>Item 9.01 Exhibits.</p>' + entry
    )
    with pytest.raises(EdgarError) as caught:
        await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert caught.value.context["reason"] == "advertised_exhibit_missing"
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_div_release_does_not_hide_a_second_advertised_missing_exhibit(monkeypatch):
    fetch = transport(monkeypatch)
    primary = (
        '<p>Item 2.02 Earnings materials are furnished as Exhibits 99.1 and 99.2.</p>'
        '<p>Item 9.01 Exhibits.</p><div><span>99.1</span>'
        '<span><a href="release.htm">Press release</a></span></div>'
    )
    with pytest.raises(EdgarError) as caught:
        await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert caught.value.context["reason"] == "advertised_exhibit_missing"
    fetch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("narrative_link", ["our website", "our press release archive"])
async def test_narrative_link_does_not_override_later_exact_exhibit_entry(monkeypatch, narrative_link):
    fetch = transport(monkeypatch)
    primary = (
        '<p>Item 2.02 Results of Operations. Our press release is furnished as Exhibit 99.1. '
        f'See <a href="https://issuer.example">{narrative_link}</a>.</p>'
        '<p>Item 9.01 Exhibits.</p><div><span>99.1 </span><span>'
        '<a href="release.htm">Press release</a></span></div>'
    )
    result = await ex.get_eightk_grounding(primary, PRIMARY_URL, CIK, ACCESSION)
    assert [member["filename"] for member in result.provenance["members"]] == ["release.htm"]
    fetch.assert_awaited_once()
