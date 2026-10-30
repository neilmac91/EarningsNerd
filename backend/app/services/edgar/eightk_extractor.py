"""Same-accession earnings exhibits for an 8-K's Item 2.02.

Selection reads the primary document already fetched by the summary pipeline. All
attachment bytes come through the existing bounded SEC transport; external links,
other accessions and missing advertised earnings exhibits never become grounding.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import re
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

from app.services.ai.recovery_context import strip_hidden_filing_nodes
from app.utils.sec_urls import build_sec_archive_url
from .async_executor import run_parse_with_timeout
from .compat import MAX_SEC_ATTACHMENT_BYTES, sec_edgar_service
from .exceptions import EdgarError

MAX_EXHIBITS = 3
MAX_GROUNDING_CHARACTERS = 120_000
MAX_PRIMARY_CHARACTERS = 2_000_000
_EXHIBIT = re.compile(r"\b(?:ex(?:hibit)?[\s-]*)?(99(?:\s*\.\s*\d+)?)\b", re.IGNORECASE)
_REFERENCED_EXHIBITS = re.compile(
    r"\bex(?:hibit)?s?[\s-]*(99(?:\s*\.\s*\d+)?(?:\s*(?:,|and|&)\s*99(?:\s*\.\s*\d+)?)*)", re.IGNORECASE,
)
_ANY_ITEM = re.compile(r"\bitems?\s*\d\s*\.\s*\d\s*\d\b", re.IGNORECASE)
_EARNINGS = re.compile(r"earnings|financial\s+results|results\s+of\s+operations|press\s+release", re.IGNORECASE)
_ITEM = re.compile(
    r"\bitems?\s*(?:\d\s*\.\s*\d\s*\d\s*(?:,|and|&)\s*)*2\s*\.\s*0\s*2\b", re.IGNORECASE,
)


@dataclass(frozen=True)
class EightKGrounding:
    text: str
    provenance: dict


def _exhibit_numbers(text: str) -> set[str]:
    return {re.sub(r"\s+", "", number) for number in _EXHIBIT.findall(text)}


def _unavailable(reason: str) -> EdgarError:
    return EdgarError(
        "The earnings release attached to this filing is not available for analysis yet",
        code="EDGAR_EARNINGS_EXHIBIT_UNAVAILABLE", context={"reason": reason},
    )


def _same_accession_filename(href: str, document_url: str, archive_url: str) -> str:
    target = urlsplit(urljoin(document_url, href))
    archive = urlsplit(archive_url)
    if (
        target.scheme != archive.scheme or target.netloc != archive.netloc or target.query
        or target.path.rsplit("/", 1)[0] + "/" != archive.path
    ):
        raise _unavailable("exhibit_outside_accession")
    filename = unquote(target.path.rsplit("/", 1)[1])
    if not filename or any(c in filename for c in "/\\?#") or filename in {".", ".."}:
        raise _unavailable("invalid_exhibit_filename")
    return filename


def _select(primary_html: str, document_url: str, cik: str, accession_number: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(primary_html, "html.parser")
    strip_hidden_filing_nodes(soup)
    text = soup.get_text(" ", strip=True)
    items = list(_ITEM.finditer(text))
    if not items:
        return text, []
    # Require every member explicitly advertised by Item 2.02; an ancillary
    # slideshow cannot stand in for a missing earnings release. Other Item
    # sections may reference unrelated exhibits and do not create this promise.
    expected: set[str] = set()
    for item in items:
        next_item = _ANY_ITEM.search(text, item.end())
        item_text = text[item.end():next_item.start() if next_item else len(text)]
        expected.update(
            number for reference in _REFERENCED_EXHIBITS.findall(item_text)
            for number in _exhibit_numbers(reference)
        )
    try:
        archive_url = build_sec_archive_url(cik, accession_number)
    except ValueError as exc:
        raise _unavailable("invalid_filing_identity") from exc
    _same_accession_filename(document_url, document_url, archive_url)
    selected: list[str] = []
    resolved: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True)
        row = anchor.find_parent("tr")
        if row is None:
            # Some filers render exhibit entries as sibling spans in a div (or
            # paragraph/list item), with only the description linked. Accept a
            # leaf entry with one exhibit identity and one link; a page wrapper
            # must never associate a distant exhibit number with another link.
            entry = anchor.find_parent(["div", "p", "li"])
            if (
                entry is not None
                and entry.find(["div", "p", "li", "tr"]) is None
                and len(entry.find_all("a", href=True)) == 1
                and len(_exhibit_numbers(entry.get_text(" ", strip=True))) == 1
            ):
                row = entry
        row_text = row.get_text(" ", strip=True) if row is not None else label
        # An exhibit-number link or its exhibit-list row identifies membership;
        # Item 2.02 alone is not permission to follow arbitrary press-release links.
        if not _EXHIBIT.search(label) and not (_EXHIBIT.search(row_text) and _EARNINGS.search(row_text)):
            continue
        numbers = _exhibit_numbers(label) or _exhibit_numbers(row_text)
        if expected and numbers.isdisjoint(expected) and not _EARNINGS.search(row_text):
            continue
        filename = _same_accession_filename(anchor["href"], document_url, archive_url)
        if filename == unquote(urlsplit(document_url).path.rsplit("/", 1)[1]):
            continue  # local anchor into the primary document, not another member
        resolved.update(numbers)
        if filename not in selected:
            selected.append(filename)
    if expected - resolved or (not selected and _EXHIBIT.search(text) and _EARNINGS.search(text)):
        raise _unavailable("advertised_exhibit_missing")
    if len(selected) > MAX_EXHIBITS:
        raise _unavailable("too_many_exhibits")
    return text, selected


def _attachment_text(content: bytes) -> str:
    if content.startswith(b"%PDF") or b"\x00" in content:
        raise _unavailable("unsupported_exhibit_format")
    soup = BeautifulSoup(content, "html.parser")
    strip_hidden_filing_nodes(soup)
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    text = soup.get_text("\n", strip=True)
    # SEC's explicit automated-tool block page is not filing content. Both its
    # title and distinctive body must match, so a filing quoting the policy passes.
    if (
        "your request originates from an undeclared automated tool" in title
        and "please declare your traffic by updating your user agent" in text.lower()
    ):
        raise _unavailable("sec_automated_tool_block")
    if not text.strip():
        raise _unavailable("empty_exhibit")
    return text


async def get_eightk_grounding(
    primary_html: str, document_url: str, cik: str, accession_number: str, *, timeout: float = 20,
) -> EightKGrounding:
    """Return unchanged primary HTML unless Item 2.02 identifies EX-99 members.

    All selected members must arrive. The shared byte cap applies to their sum,
    and a total deadline covers attachment pacing, reads and local extraction.
    Oversized grounding fails explicitly; no financial table is silently cut.
    """
    try:
        async with asyncio.timeout(timeout):
            return await _get_eightk_grounding(primary_html, document_url, cik, accession_number, timeout)
    except TimeoutError as exc:
        raise _unavailable("exhibit_deadline") from exc


async def _get_eightk_grounding(
    primary_html: str, document_url: str, cik: str, accession_number: str, timeout: float,
) -> EightKGrounding:
    if len(primary_html) > MAX_PRIMARY_CHARACTERS:
        raise _unavailable("primary_document_too_large")
    primary_text, filenames = await run_parse_with_timeout(
        lambda: _select(primary_html, document_url, cik, accession_number), timeout,
    )
    provenance = {
        "schema_version": 1, "source": "eightk_same_accession_v1", "accession_number": accession_number,
        "primary_document_url": document_url,
        "primary_decoded_sha256": hashlib.sha256(primary_html.encode("utf-8")).hexdigest(),
        "members": [],
    }
    if not filenames:
        return EightKGrounding(primary_html, provenance)
    remaining_bytes = MAX_SEC_ATTACHMENT_BYTES
    parts = [f"8-K primary document\n{primary_text}"]
    for filename in filenames:
        if remaining_bytes <= 0:
            raise _unavailable("exhibit_byte_budget")
        content, source = await sec_edgar_service.get_filing_attachment_bytes(
            cik, accession_number, filename, timeout=timeout, max_retries=1, max_bytes=remaining_bytes,
        )
        remaining_bytes -= len(content)
        text = await run_parse_with_timeout(lambda: _attachment_text(content), timeout)
        parts.append(f"Same-filing attachment: {filename}\n{text}")
        provenance["members"].append({
            **source, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text_characters": len(text),
        })
        if sum(len(part) for part in parts) > MAX_GROUNDING_CHARACTERS:
            raise _unavailable("earnings_grounding_too_large")
    # Preserve plain text literally through the downstream HTML-to-text extractor.
    return EightKGrounding("<pre>" + html.escape("\n\n".join(parts)) + "</pre>", provenance)
