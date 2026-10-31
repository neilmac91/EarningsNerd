"""SEC inputs for evidence packs, fetched through the application's own transports and cached.

- ``annual_reports``: the company's 10-K filings (``edgar.compat.sec_edgar_service.get_filings``).
- ``document_text``: a 10-K primary document (``get_filing_document``) parsed locally with edgartools'
  HTML parser, the same parser ``edgar.xbrl_sections`` uses for summary sections.
- ``dimensional_facts``: a 10-K's own XBRL instance (``edgar.client.resolve_filing_by_accession`` ->
  ``filing.xbrl()``), reduced to the dimensioned duration facts of the concepts the driver tree reads.
- ``fulltext_hits``: EDGAR full-text search (``integrations.sec_api.SECFullTextSearchClient``).

Every result is cached under ``bootstrap.CACHE`` by accession (or query), so packs rebuild from the
same bytes. Nothing here writes to the facts store.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import re
from typing import Any, Optional

from evals.trend_depth import bootstrap

# Concepts whose dimensioned facts the driver tree reads: revenue lines, segment profit, cost lines.
DIMENSION_CONCEPTS: tuple[str, ...] = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "RevenueFromCollaborativeArrangementExcludingRevenueFromContractWithCustomer",
    "OperatingIncomeLoss",
    "SegmentReportingInformationProfitLoss",
    "GrossProfit",
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "ResearchAndDevelopmentExpense",
    "SellingGeneralAndAdministrativeExpense",
    "NetIncomeLoss",
    "InterestIncomeExpenseNet",
    "NoninterestIncome",
    "NoninterestExpense",
    "ProvisionForLoanLeaseAndOtherLosses",
    "PremiumsEarnedNet",
)


async def annual_reports(cik: str, companyfacts: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """10-K filings (no amendments), newest first, with document URLs built by the app.

    The app's filing list reads the submissions "recent" block, which for a heavy filer (JPMorgan files
    thousands of prospectus supplements a year) holds only the latest 10-K. Older 10-K accessions are
    taken from companyfacts (every fact carries the accession and form that reported it) and resolved
    through ``edgar.client.resolve_filing_by_accession`` for their primary document.
    """
    name = f"filings/CIK{cik.zfill(10)}-10K-v2.json"
    cached = bootstrap.read_cached(name)
    if cached is not None:
        return cached
    from app.services.edgar.compat import sec_edgar_service

    filings = await sec_edgar_service.get_filings(cik.zfill(10), ["10-K"], limit=16)
    rows = [
        {
            "accession": f["accession_number"],
            "form": f["filing_type"],
            "filed": f["filing_date"],
            "period_end": f.get("period_end_date") or f.get("report_date"),
            "document_url": f["document_url"],
            "folder_url": f["sec_url"],
        }
        for f in filings
        if f.get("filing_type") == "10-K"
    ]
    if companyfacts is not None:
        known = {row["accession"] for row in rows}
        for accession, (filed, period_end) in _companyfacts_10k_accessions(companyfacts).items():
            if accession in known:
                continue
            resolved = await asyncio.to_thread(_resolve_primary_document, cik, accession)
            if resolved:
                rows.append({"accession": accession, "form": "10-K", "filed": filed, "period_end": period_end,
                             "document_url": resolved[0], "folder_url": resolved[1]})
        rows.sort(key=lambda row: row["filed"], reverse=True)
    bootstrap.write_cached(name, rows)
    return rows


def _companyfacts_10k_accessions(payload: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """accession -> (filed, fiscal period end) for every original 10-K that reported annual facts."""
    from datetime import date

    out: dict[str, tuple[str, str]] = {}
    for concept in (payload.get("facts", {}).get("us-gaap", {}) or {}).values():
        for rows in (concept.get("units") or {}).values():
            for row in rows:
                if row.get("form") != "10-K" or row.get("fp") != "FY" or not row.get("accn"):
                    continue
                start, end = row.get("start"), row.get("end")
                if not start or not end:
                    continue
                if not 320 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 390:
                    continue
                filed, current = out.get(row["accn"], (row.get("filed") or "", ""))
                out[row["accn"]] = (filed, max(current, end))
    return out


def _resolve_primary_document(cik: str, accession: str) -> Optional[tuple[str, str]]:
    from urllib.parse import urljoin

    from app.services.edgar.client import resolve_filing_by_accession
    from app.utils.sec_urls import build_sec_archive_url

    try:
        _company, filings = resolve_filing_by_accession(cik.zfill(10), accession)
    except Exception:  # noqa: BLE001 - an accession edgartools cannot resolve is left out
        return None
    if not filings:
        return None
    primary = getattr(filings[0], "primary_document", None)
    if not primary:
        return None
    folder = build_sec_archive_url(cik, accession)
    return urljoin(folder, primary), folder


async def document_text(filing: dict[str, Any], cik: Optional[str] = None) -> dict[str, Any]:
    """The 10-K's parsed text: whole document plus the MD&A section, with the parser's output only.

    Some filers (US Bancorp among the banks examined) incorporate MD&A by reference from the annual
    report filed as Exhibit 13, so the primary document's Item 7 is a one-line pointer. When the parsed
    MD&A is that short, the EX-13 attachment is fetched through the app's attachment transport and its
    text stands in for the MD&A (``mda_source`` and ``mda_url`` record where it came from).
    """
    name = f"documents/{filing['accession']}.json"
    cached = bootstrap.read_cached(name)
    if cached is not None and (len(cached.get("mda") or "") >= 2000 or not cik):
        return cached
    if cached is not None and cached.get("ex13_checked"):
        if len(cached.get("mda") or "") < 2000 and not cached.get("mda_slice_checked"):
            cached = _slice_item_7(cached)
            bootstrap.write_cached(name, cached)
        return cached
    from edgar.documents import parse_html

    from app.services.edgar.compat import sec_edgar_service
    from app.services.edgar.xbrl_sections import _sections_from_html

    if cached is None:
        html = await sec_edgar_service.get_filing_document(filing["document_url"])

        def parse() -> dict[str, Any]:
            sections = _sections_from_html(html, "10-K") or {}
            try:
                full = parse_html(html).text()
            except Exception:  # noqa: BLE001 - a document the parser cannot read keeps its MD&A only
                full = ""
            return {"mda": sections.get("mda", ""), "full": full, "html_chars": len(html)}

        parsed = await asyncio.to_thread(parse)
    else:
        parsed = dict(cached)
    if len(parsed.get("mda") or "") < 2000 and cik:
        parsed["ex13_checked"] = True
        exhibit = await asyncio.to_thread(_exhibit_13_name, cik, filing["accession"])
        if exhibit:
            body, _meta = await sec_edgar_service.get_filing_attachment_bytes(cik.zfill(10), filing["accession"], exhibit)
            ex_html = body.decode("utf-8", "replace")
            ex_text = await asyncio.to_thread(lambda: parse_html(ex_html).text())
            parsed["mda"] = ex_text
            parsed["mda_source"] = "EX-13"
            parsed["mda_url"] = filing["folder_url"].rstrip("/") + "/" + exhibit
            parsed["full"] = (parsed.get("full") or "") + "\n\n" + ex_text
    if len(parsed.get("mda") or "") < 2000:
        parsed = _slice_item_7(parsed)
    bootstrap.write_cached(name, parsed)
    return parsed


_ITEM_7 = re.compile(
    r"item\s*7\.?\s*[-–—:]?\s*management.{0,3}s\s+discussion|^\s*management.{0,3}s discussion and analysis\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_ITEM_END = re.compile(
    r"item\s*(7a|8)\.?\s*[-–—:]?\s*(quantitative|financial\s+statements)|report of independent registered public "
    r"accounting firm|^\s*statements? of consolidated (income|operations)",
    re.IGNORECASE | re.MULTILINE,
)


def _slice_item_7(parsed: dict[str, Any]) -> dict[str, Any]:
    """MD&A cut from the full text when the section parser found none: the longest span from an
    "Item 7. Management's Discussion" heading, or a free-standing "MANAGEMENT'S DISCUSSION AND ANALYSIS"
    heading (Deere prints its MD&A after Item 16 and points Item 7 at it), to the next Item 7A or Item 8
    heading, auditor's report or consolidated statement. The longest span skips the table of contents."""
    parsed = {**parsed, "mda_slice_checked": True}
    full = parsed.get("full") or ""
    best = ""
    for start in _ITEM_7.finditer(full):
        end = _ITEM_END.search(full, start.end())
        span = full[start.start():end.start() if end else min(len(full), start.start() + 400_000)]
        if len(span) > len(best):
            best = span
    if len(best) >= 5000:
        parsed["mda"] = best
        parsed["mda_source"] = "item-7-slice"
    return parsed


def _exhibit_13_name(cik: str, accession: str) -> Optional[str]:
    from app.services.edgar.client import resolve_filing_by_accession

    try:
        _company, filings = resolve_filing_by_accession(cik.zfill(10), accession)
    except Exception:  # noqa: BLE001 - no attachment list, no exhibit
        return None
    if not filings:
        return None
    try:
        attachments = list(filings[0].attachments)
    except Exception:  # noqa: BLE001 - SEC sometimes answers the submission file with an HTML error page
        return None
    for attachment in attachments:
        if str(getattr(attachment, "document_type", "")).upper().startswith("EX-13"):
            return getattr(attachment, "document", None)
    return None


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


async def dimensional_facts(cik: str, accession: str) -> list[dict[str, Any]]:
    """Dimensioned duration facts of ``DIMENSION_CONCEPTS`` from the filing's own XBRL instance."""
    name = f"xbrl-dims/{accession}.json"
    cached = bootstrap.read_cached(name)
    if cached is not None:
        return cached
    from app.services.edgar.client import resolve_filing_by_accession

    def extract() -> list[dict[str, Any]]:
        _company, filings = resolve_filing_by_accession(cik.zfill(10), accession)
        if not filings:
            return []
        xb = filings[0].xbrl()
        if xb is None:
            return []
        frame = xb.facts.to_dataframe()
        if frame is None or frame.empty:
            return []
        frame = frame[frame["is_dimensioned"].fillna(False).astype(bool)]
        local = frame["concept"].astype(str).str.split(":").str[-1]
        frame = frame[local.isin(DIMENSION_CONCEPTS) & frame["period_start"].notna()]
        dim_cols = [c for c in frame.columns if c.startswith("dim_")]
        rows: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            dims = {
                col[4:]: str(row[col]) for col in dim_cols if _clean(row[col]) is not None
            }
            if not dims or _clean(row.get("numeric_value")) is None:
                continue
            rows.append(
                {
                    "concept": str(row["concept"]).split(":")[-1],
                    "start": str(row["period_start"])[:10],
                    "end": str(row["period_end"])[:10],
                    "value": float(row["numeric_value"]),
                    "unit": _clean(row.get("unit_ref")),
                    "decimals": _clean(row.get("decimals")),
                    "dims": dims,
                    "member_label": _clean(row.get("dimension_member_label")) or _clean(row.get("label")),
                    "label": _clean(row.get("label")),
                }
            )
        return rows

    rows = await asyncio.to_thread(extract)
    bootstrap.write_cached(name, rows)
    return rows


async def fulltext_hits(query: str, cik: str, start_date: str, end_date: str, forms: str = "10-K") -> list[dict[str, Any]]:
    """Filings of this company that mention ``query`` (EDGAR full-text search), cached by query."""
    key = hashlib.sha256(f"{query}|{cik}|{start_date}|{end_date}|{forms}".encode()).hexdigest()[:24]
    name = f"efts/{key}.json"
    cached = bootstrap.read_cached(name)
    if cached is not None:
        return cached["hits"]
    from app.integrations.sec_api import SECFullTextSearchClient

    result = await SECFullTextSearchClient().search(
        query=f'"{query}"', forms=forms, start_date=start_date, end_date=end_date, ciks=cik.zfill(10),
    )
    rows = [
        {
            "accession": hit.accession_no,
            "form": hit.form,
            "filed": hit.filed_date,
            "period_ending": hit.period_ending,
            "document_url": hit.document_url,
        }
        for hit in result.hits
    ]
    payload = {"query": query, "total": result.total, "hits": rows}
    bootstrap.write_cached(name, payload)
    return payload["hits"]


def find_filing(reports: list[dict[str, Any]], period_end: str) -> Optional[dict[str, Any]]:
    """The 10-K whose fiscal period ends on ``period_end`` (within a week, for 52/53-week years)."""
    from datetime import date

    target = date.fromisoformat(period_end[:10])
    best = None
    for report in reports:
        if not report.get("period_end"):
            continue
        gap = abs((date.fromisoformat(report["period_end"][:10]) - target).days)
        if gap <= 7 and (best is None or gap < best[0]):
            best = (gap, report)
    return best[1] if best else None
