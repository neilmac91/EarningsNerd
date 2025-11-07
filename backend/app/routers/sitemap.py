from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Company
from datetime import datetime

router = APIRouter()

@router.get("/sitemap.xml")
async def generate_sitemap(db: Session = Depends(get_db)):
    """Generate XML sitemap for all companies"""
    base_url = "https://earningsnerd.com"  # Update with your actual domain
    
    # Get all companies
    companies = db.query(Company).all()
    
    # Generate sitemap XML
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # Add homepage
    sitemap += '  <url>\n'
    sitemap += f'    <loc>{base_url}/</loc>\n'
    sitemap += f'    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n'
    sitemap += '    <changefreq>daily</changefreq>\n'
    sitemap += '    <priority>1.0</priority>\n'
    sitemap += '  </url>\n'
    
    # Add pricing page
    sitemap += '  <url>\n'
    sitemap += f'    <loc>{base_url}/pricing</loc>\n'
    sitemap += f'    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n'
    sitemap += '    <changefreq>weekly</changefreq>\n'
    sitemap += '    <priority>0.8</priority>\n'
    sitemap += '  </url>\n'
    
    # Add company pages
    for company in companies:
        sitemap += '  <url>\n'
        sitemap += f'    <loc>{base_url}/company/{company.ticker}</loc>\n'
        sitemap += f'    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n'
        sitemap += '    <changefreq>weekly</changefreq>\n'
        sitemap += '    <priority>0.7</priority>\n'
        sitemap += '  </url>\n'
    
    sitemap += '</urlset>'
    
    return Response(content=sitemap, media_type="application/xml")

