"""P1-9 guardrail (data-quality plan): the weekly data-quality report.

Seeded fixtures exercise all four detection sections (ticker integrity, coverage gaps, filing
anomalies, partial-summary reasons) + the email render, so a change that silently breaks a section
fails CI. ORM-only (no raw SQL) — runs on the in-memory SQLite suite DB.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Company, Filing, FinancialFact, Summary
from app.services import data_quality_service, email_service


def _session():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng)()


def _fact(company_id, concept, fy, *, unit="USD"):
    return FinancialFact(
        company_id=company_id, concept=concept, unit=unit,
        period_end=date(fy, 12, 31), fiscal_year=fy, fiscal_period="FY",
        value=1, accession=f"acc-{company_id}-{concept}-{fy}", is_latest=True,
    )


@pytest.fixture()
def seeded(monkeypatch):
    db = _session()
    # (a) JPMX stored under a wrong ticker (primary is JPM); GONE is delisted (absent from SEC file).
    jpmx = Company(cik="0000019617", ticker="JPMX", name="JPMorgan")
    gone = Company(cik="0009999999", ticker="GONE", name="Delisted Co")
    # (b) GAP: total_assets through FY2024 but cash only through FY2018 → a cash coverage gap.
    gap = Company(cik="0000000111", ticker="GAP", name="Gap Co")
    # (c) ANOM: deep fact history (2006–2024) but no stored 10-K rows.
    anom = Company(cik="0000000222", ticker="ANOM", name="Anomaly Co")
    # (d) PART: a partial-tier summary with a grounding reason.
    part = Company(cik="0000000333", ticker="PART", name="Partial Co", sic="6021")
    db.add_all([jpmx, gone, gap, anom, part])
    db.commit()

    # GAP facts: assets FY2022+FY2024, cash only FY2018 (+ 3 stored 10-Ks so it is NOT an anomaly).
    db.add_all([
        _fact(gap.id, "total_assets", 2022), _fact(gap.id, "total_assets", 2024),
        _fact(gap.id, "cash_and_equivalents", 2018),
    ])
    for i in range(3):
        db.add(Filing(company_id=gap.id, accession_number=f"gap-10k-{i}", filing_type="10-K",
                      filing_date=date(2022 + i, 2, 1),
                      document_url="https://x/d.htm", sec_url="https://x/"))
    # ANOM facts: assets 2006 & 2024 (span 18), no filings.
    db.add_all([_fact(anom.id, "total_assets", 2006), _fact(anom.id, "total_assets", 2024)])
    # PART: a filing + a partial summary.
    pf = Filing(company_id=part.id, accession_number="part-10k", filing_type="10-K",
                filing_date=date(2024, 2, 1), document_url="https://x/d.htm", sec_url="https://x/")
    db.add(pf)
    db.commit()
    db.add(Summary(filing_id=pf.id, raw_summary={
        "quality": {"tier": "partial", "reasons": ["financial figures not grounded in SEC XBRL data"]}
    }))
    db.commit()

    async def fake_primary(cik):
        return {
            "0000019617": "JPM", "0000000111": "GAP",
            "0000000222": "ANOM", "0000000333": "PART",
        }.get(cik)  # GONE's CIK absent → None (delisted)

    from app.services.edgar.compat import sec_edgar_service
    monkeypatch.setattr(sec_edgar_service, "primary_ticker_for_cik", fake_primary)
    yield db
    db.close()


@pytest.mark.asyncio
async def test_report_populates_all_four_sections(seeded):
    report = await data_quality_service.build_report(seeded)

    # (a) ticker integrity
    assert {"ticker": "JPMX", "primary": "JPM", "cik": "0000019617"} in report["ticker_mismatches"]
    assert {"ticker": "GONE", "cik": "0009999999"} in report["ticker_not_in_file"]

    # (b) coverage gap: GAP's cash lags total_assets (2024) — a cash_and_equivalents gap.
    cash_gaps = [g for g in report["coverage_gaps"] if g["ticker"] == "GAP" and g["concept"] == "cash_and_equivalents"]
    assert cash_gaps and cash_gaps[0]["last_fy"] == 2018 and cash_gaps[0]["last_total_assets_fy"] == 2024

    # (c) filing anomaly: ANOM has a deep fact span and no stored 10-Ks; GAP (3 10-Ks) does not.
    anom_tickers = {a["ticker"] for a in report["filing_anomalies"]}
    assert "ANOM" in anom_tickers
    assert "GAP" not in anom_tickers

    # (d) partial-summary reasons: PART's grounding reason bucketed by SIC prefix "60".
    assert {"sic_prefix": "60", "reason": "financial figures not grounded in SEC XBRL data", "count": 1} in report["partial_reasons"]


@pytest.mark.asyncio
async def test_report_email_renders_html_and_text(seeded):
    report = await data_quality_service.build_report(seeded)
    html, text = email_service.render_data_quality_report(report)

    assert "Ticker mismatches" in html and "Coverage gaps" in html
    assert "JPMX" in html and "JPM" in html  # the mismatch surfaces in the email
    assert "Automated weekly scan" in html  # our report body, wrapped in the brand chrome
    # Text alternative carries the same signal for plain-text clients.
    assert "Ticker mismatches: 1" in text
    assert "financial figures not grounded in SEC XBRL data" in text


def test_render_handles_an_all_clean_report():
    empty = {
        "ticker_mismatches": [], "ticker_not_in_file": [],
        "coverage_gaps": [], "filing_anomalies": [], "partial_reasons": [],
    }
    html, text = email_service.render_data_quality_report(empty)
    assert "None — clean" in html
    assert "Ticker mismatches: 0" in text
