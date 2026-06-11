from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Company, Filing
from datetime import datetime

router = APIRouter()

# Static frontend routes worth indexing: (path, changefreq, priority)
STATIC_PAGES = [
    ("/", "daily", "1.0"),
    ("/pricing", "weekly", "0.8"),
    ("/contact", "monthly", "0.5"),
    ("/privacy", "yearly", "0.3"),
    ("/security", "yearly", "0.3"),
]


def _url_entry(loc: str, lastmod: str, changefreq: str, priority: str) -> str:
    return (
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>\n"
    )


@router.get("/sitemap.xml")
async def generate_sitemap(db: Session = Depends(get_db)):
    """Generate XML sitemap: static pages + company pages + filing pages
    (the long-tail SEO asset: every ticker x every filing)."""
    base_url = "https://www.earningsnerd.io"
    today = datetime.now().strftime("%Y-%m-%d")

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for path, changefreq, priority in STATIC_PAGES:
        sitemap += _url_entry(f"{base_url}{path}", today, changefreq, priority)

    for company in db.query(Company).all():
        sitemap += _url_entry(
            f"{base_url}/company/{company.ticker}", today, "weekly", "0.7"
        )

    for filing_id, filing_date in db.query(Filing.id, Filing.filing_date).all():
        lastmod = filing_date.strftime("%Y-%m-%d") if filing_date else today
        sitemap += _url_entry(f"{base_url}/filing/{filing_id}", lastmod, "monthly", "0.6")

    sitemap += '</urlset>'

    return Response(content=sitemap, media_type="application/xml")

