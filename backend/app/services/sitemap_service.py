"""Sitemap eligibility queries and XML assembly; the HTTP router owns caching."""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Company, Filing, Summary
from app.services.company_coverage import unsupported_foreign_name
from app.services.summary_placeholders import IN_PROGRESS_MARKER, SUMMARY_FAILURE_TOKENS

BASE_URL = "https://www.earningsnerd.io"

# Static frontend routes worth indexing: (path, changefreq, priority)
STATIC_PAGES = [
    ("/", "daily", "1.0"),
    ("/pricing", "weekly", "0.8"),
    ("/contact", "monthly", "0.5"),
    ("/privacy", "yearly", "0.3"),
    ("/terms", "yearly", "0.3"),
    ("/security", "yearly", "0.3"),
]

# Whole-document bound with headroom under the 50k-URL protocol cap: static pages always,
# then companies (newest filing first), then filings (newest first) until the budget is spent.
MAX_SITEMAP_URLS = 45_000

def _url_entry(loc: str, changefreq: str, priority: str, lastmod: str | None = None) -> str:
    lastmod_line = f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
    return (
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"{lastmod_line}"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>\n"
    )


def _sort_stamp(value: datetime | None) -> float:
    """Order key for a nullable date: a missing date sorts last (oldest)."""
    return value.timestamp() if value is not None else float("-inf")


def _build_sitemap(db: Session) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n',
    ]

    for path, changefreq, priority in STATIC_PAGES:
        parts.append(_url_entry(f"{BASE_URL}{path}", changefreq, priority))
    budget = max(MAX_SITEMAP_URLS - len(STATIC_PAGES), 0)

    # Companies with at least one filing (an empty company page is a stub not worth crawling);
    # lastmod = the newest filing's date, i.e. the last time the page's content actually changed.
    company_rows = (
        db.query(Company.ticker, func.max(Filing.filing_date))
        .join(Filing, Filing.company_id == Company.id)
        .group_by(Company.ticker)
        .all()
    )
    companies = [
        (ticker.upper(), latest_filing_date)
        for ticker, latest_filing_date in company_rows
        if ticker and unsupported_foreign_name(ticker) is None
    ]
    # Newest content first so the bound drops the least-recently-changed pages; the ticker
    # breaks ties so the document is deterministic across rebuilds.
    companies.sort(key=lambda row: row[0])
    companies.sort(key=lambda row: _sort_stamp(row[1]), reverse=True)
    for ticker, latest_filing_date in companies[:budget]:
        lastmod = latest_filing_date.strftime("%Y-%m-%d") if latest_filing_date else None
        parts.append(_url_entry(f"{BASE_URL}/company/{ticker}", "weekly", "0.7", lastmod))
    budget -= min(len(companies), budget)

    # Only filings with a generated summary: the frontend noindexes summary-less filing pages
    # (they are signup-gate stubs), and advertising noindex'd URLs wastes crawl budget.
    filing_rows = [] if budget == 0 else (
        db.query(Filing.id, Filing.filing_date)
        .join(Summary, Summary.filing_id == Filing.id)
        .filter(Summary.business_overview.isnot(None))
        .filter(Summary.business_overview != "")
        # The filing page's readiness rule (summary_placeholders.is_summary_ready, which
        # serverApi.ts::summaryHasDisplayableContent mirrors for noindex), before applying the cap.
        # REPLACE is case-sensitive on SQLite and PostgreSQL, unlike SQLite LIKE.
        .filter(
            func.replace(Summary.business_overview, IN_PROGRESS_MARKER, "")
            == Summary.business_overview
        )
        .filter(*(func.lower(Summary.business_overview).notlike(f"%{token}%") for token in SUMMARY_FAILURE_TOKENS))
        .filter(Summary.raw_summary["writer_error"].as_string().is_(None))
        .order_by(Filing.filing_date.desc(), Filing.id.desc())
        .limit(budget)
        .all()
    )
    for filing_id, filing_date in filing_rows:
        lastmod = filing_date.strftime("%Y-%m-%d") if filing_date else None
        parts.append(_url_entry(f"{BASE_URL}/filing/{filing_id}", "monthly", "0.6", lastmod))

    parts.append("</urlset>")
    return "".join(parts)
