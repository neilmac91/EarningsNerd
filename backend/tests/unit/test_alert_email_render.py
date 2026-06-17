"""Alert/digest email rendering: contains the public filing fields, never the recipient's email."""
from app.services.email_service import render_daily_digest, render_new_filing_alert


def test_new_filing_alert_contains_public_fields_and_link():
    html, text = render_new_filing_alert(
        name="Jane",
        company_name="Acme Corp",
        ticker="ACME",
        filing_type="10-Q",
        filing_date="2026-06-16",
        filing_id=42,
    )
    for needle in ("Acme Corp", "ACME", "10-Q", "2026-06-16", "/filing/42"):
        assert needle in html
        assert needle in text or needle == "/filing/42"  # link present in both
    assert "/filing/42" in text


def test_new_filing_alert_has_no_recipient_email_pii():
    # The renderer never receives the recipient email, so it can't leak into the body. Guard it.
    html, text = render_new_filing_alert(
        name="Jane",
        company_name="Acme Corp",
        ticker="ACME",
        filing_type="8-K",
        filing_date="2026-06-16",
        filing_url="https://www.sec.gov/x/",
    )
    assert "@" not in html
    assert "@" not in text


def test_daily_digest_lists_each_filing():
    items = [
        {"company_name": "Acme Corp", "ticker": "ACME", "filing_type": "10-Q",
         "filing_date": "2026-06-16", "filing_id": 1},
        {"company_name": "Globex", "ticker": "GBX", "filing_type": "8-K",
         "filing_date": "2026-06-15", "filing_id": 2},
    ]
    html, text = render_daily_digest(name=None, items=items)
    for needle in ("ACME", "GBX", "10-Q", "8-K", "/filing/1", "/filing/2"):
        assert needle in html
    assert "@" not in html
