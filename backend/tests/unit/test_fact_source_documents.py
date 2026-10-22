"""E149: a fact's source link opens its filing's primary document, not the accession folder.

``fact_provenance`` links each reported value and each calculation operand that stores no link.
Given a lookup (dashless accession to the filing row's ``document_url``) it takes that filing's
document when it is an SEC archive URL inside the accession's folder; any other accession keeps
its folder (``build_sec_archive_url``), and a call without the lookup links every one to its
folder, as before. The Multi-Period dataset builds the lookup with one read of the company's
filing rows (``trend_analysis/source_documents.py``), so its points, their operands, their
comparisons and the narrative's citations open the document. Its snapshot fingerprint hashes each
looked-up link as its folder, so a filing row that lands moves no snapshot; a link stored with its
receipt is hashed as stored.

Synthetic fixtures, not real-issuer coverage.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.database import SessionLocal
from app.models import Company, Filing, FinancialFact
from app.services import trend_analysis_service as svc
from app.services.fact_provenance import calculated_provenance, provenance_for_fact, reported_provenance
from app.services.trend_analysis.presentation import _operand
from app.services.trend_analysis.source_documents import folder_links
from app.utils.sec_urls import build_sec_archive_url, normalize_accession

CIK = "1326801"
ANNUAL = "0001326801-25-000010"
NINE_MONTHS = "0001326801-24-000091"
UNLISTED = "0001326801-24-000077"


def _document(cik, accession, name):
    """A primary document under the filing's folder, as the edgar client stores ``document_url``."""
    return build_sec_archive_url(cik, accession) + name


DOCUMENTS = {
    normalize_accession(ANNUAL): _document(CIK, ANNUAL, "annual-10k.htm"),
    normalize_accession(NINE_MONTHS): _document(CIK, NINE_MONTHS, "third-quarter-10q.htm"),
}


def _fact(**changes):
    return {
        "concept": "revenue", "value": Decimal("42000000000"), "unit": "USD",
        "period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31),
        "accession": ANNUAL, "raw_tag": "us-gaap:Revenues",
        "fiscal_year": 2024, "fiscal_period": "FY",
        "filed_at": "2025-01-30", "source": "companyfacts", "reconciled": True,
        "provenance": None, **changes,
    }


@pytest.mark.parametrize("spelling", [ANNUAL, normalize_accession(ANNUAL)], ids=["dashed", "dashless"])
def test_a_reported_fact_opens_its_filings_document(spelling):
    provenance = provenance_for_fact(_fact(accession=spelling), CIK, DOCUMENTS)
    assert provenance["method"] == "reported"
    assert provenance["source_url"] == _document(CIK, ANNUAL, "annual-10k.htm")


def test_each_operand_opens_its_own_filings_document_nested_ones_included():
    annual = _fact()
    nine_months = _fact(value=Decimal("30000000000"), period_end=date(2024, 9, 30), accession=NINE_MONTHS)
    quarter = _fact(
        source="derived", value=Decimal("12000000000"), period_start=date(2024, 10, 1), fiscal_period="Q4",
        provenance=calculated_provenance("FY - YTD9", [annual, nine_months]),
    )
    nested = _fact(
        concept="free_cash_flow", source="derived",
        provenance=calculated_provenance("operating_cash_flow - capex", [quarter, _fact(value=5)]),
    )
    projected = provenance_for_fact(nested, CIK, DOCUMENTS)
    assert "source_url" not in projected  # A computed value is not a reported filing row.
    outer = projected["inputs"]
    assert [item["source_url"] for item in outer] == [_document(CIK, ANNUAL, "annual-10k.htm")] * 2
    inner = outer[0]["provenance"]["inputs"]
    assert [item["source_url"] for item in inner] == [
        _document(CIK, ANNUAL, "annual-10k.htm"), _document(CIK, NINE_MONTHS, "third-quarter-10q.htm"),
    ]


def test_an_accession_with_no_filing_row_keeps_its_folder():
    folder = build_sec_archive_url(CIK, UNLISTED)
    assert provenance_for_fact(_fact(accession=UNLISTED), CIK, DOCUMENTS)["source_url"] == folder
    calculation = _fact(concept="free_cash_flow", source="derived", provenance=calculated_provenance(
        "operating_cash_flow - capex", [_fact(accession=UNLISTED), _fact()],
    ))
    inputs = provenance_for_fact(calculation, CIK, DOCUMENTS)["inputs"]
    assert [item["source_url"] for item in inputs] == [folder, _document(CIK, ANNUAL, "annual-10k.htm")]
    # Without the lookup every caller's links are the folders they were.
    assert provenance_for_fact(_fact(), CIK)["source_url"] == build_sec_archive_url(CIK, ANNUAL)
    assert provenance_for_fact(calculation, CIK) == provenance_for_fact(calculation, CIK, {})
    assert "source_url" not in provenance_for_fact(_fact(accession="synthetic-quarter"), CIK, DOCUMENTS)


def test_a_stored_source_link_is_kept():
    stored = _document(CIK, ANNUAL, "reported-eps-exhibit.htm")
    fact = _fact(provenance={**reported_provenance(_fact()), "source_url": stored})
    assert provenance_for_fact(fact, CIK, DOCUMENTS)["source_url"] == stored
    operand = _fact(accession=NINE_MONTHS, provenance={**reported_provenance(_fact()), "source_url": stored})
    calculation = _fact(source="derived", provenance=calculated_provenance("FY - YTD9", [_fact(), operand]))
    inputs = provenance_for_fact(calculation, CIK, DOCUMENTS)["inputs"]
    assert [item["source_url"] for item in inputs] == [_document(CIK, ANNUAL, "annual-10k.htm"), stored]


@pytest.mark.parametrize("stored", [
    "https://www.sec.gov/cgi-bin/viewer?action=view&cik=1326801&accession_number=0001326801-25-000010",
    "https://sec.example/Archives/edgar/data/1326801/000132680125000010/annual-10k.htm",
    _document("320193", ANNUAL, "annual-10k.htm"),
], ids=["legacy-viewer", "another-host", "another-ciks-folder"])
def test_a_stored_document_outside_the_accession_folder_keeps_the_folder(stored):
    """The filings table keeps legacy viewer rows and other hosts; only this folder's document counts."""
    documents = {normalize_accession(ANNUAL): stored}
    assert provenance_for_fact(_fact(), CIK, documents)["source_url"] == build_sec_archive_url(CIK, ANNUAL)


@pytest.fixture
def dataset_db():
    """Two companies of their own inside one rollback-only transaction."""
    with SessionLocal() as db:
        token = uuid.uuid4().hex
        company = Company(cik=str(int(token[:12], 16)), ticker=f"DOCS{token[:8]}", name="Synthetic documents fixture")
        other = Company(cik=str(int(token[:12], 16) + 1), ticker=f"ELSE{token[:8]}", name="Another filer")
        db.add_all([company, other])
        db.flush()
        yield db, company, other, f"{int(token[12:20], 16) % 9_000_000_000 + 1_000_000_000}"
        db.rollback()


def _filing(db, company, accession, name, form="10-Q", document_url=None):
    db.add(Filing(
        company_id=company.id, accession_number=accession, filing_type=form,
        filing_date=datetime(2025, 1, 30, tzinfo=timezone.utc),
        sec_url=build_sec_archive_url(company.cik, accession),
        document_url=document_url or _document(company.cik, accession, name),
    ))


def _quarter(db, company, concept, value, quarter, accession, **changes):
    months = {3: (7, 9, 30), 4: (10, 12, 31)}
    start_month, end_month, end_day = months[quarter]
    db.add(FinancialFact(**{
        "company_id": company.id, "concept": concept, "value": Decimal(str(value)), "unit": "USD",
        "period_start": date(2024, start_month, 1), "period_end": date(2024, end_month, end_day),
        "fiscal_year": 2024, "fiscal_period": f"Q{quarter}", "form": "10-Q", "accession": accession,
        "raw_tag": f"us-gaap:{concept}", "source": "companyfacts", "reconciled": True, "is_latest": True,
        **changes,
    }))


def _points(dataset, concept):
    series = next(item for item in dataset["series"] if item["concept"] == concept)
    return {point["period"]: point for point in series["points"]}


def _seed(db, company, other, prefix):
    """The window's facts and filing rows; returns each accession by its role."""
    acc = {role: f"{prefix}-{number}" for role, number in (
        ("annual", "25-000010"), ("original_q3", "24-000091"), ("later_q3", "25-000072"),
        ("unlisted", "24-000077"), ("elsewhere", "25-000033"), ("offsite", "24-000055"), ("eps_8k", "24-000066"),
    )}
    # Filing rows: the 10-K dashed, the later 10-Q dashless, another company's row for `elsewhere`,
    # and a row whose document is on another host.
    _filing(db, company, acc["annual"], "annual-10k.htm", "10-K")
    _filing(db, company, acc["original_q3"], "original-q3-10q.htm")
    _filing(db, company, normalize_accession(acc["later_q3"]), "later-q3-10q.htm")
    _filing(db, other, acc["elsewhere"], "another-filers-10k.htm", "10-K")
    _filing(db, company, acc["offsite"], "", document_url="https://sec.example/mirror/offsite-10q.htm")
    # Q3 revenue is the later 10-Q's comparative; the derived Q4 cites the 10-K (dashless) and the
    # original Q3 10-Q, which no row in the window names.
    _quarter(db, company, "revenue", 100, 3, acc["later_q3"])
    operands = [
        {"concept": "revenue", "value": 420, "unit": "USD", "period_start": date(2024, 1, 1),
         "period_end": date(2024, 12, 31), "accession": normalize_accession(acc["annual"]),
         "raw_tag": "us-gaap:Revenues", "source": "companyfacts", "reconciled": True, "filed_at": "2025-01-30"},
        {"concept": "revenue", "value": 300, "unit": "USD", "period_start": date(2024, 1, 1),
         "period_end": date(2024, 9, 30), "accession": acc["original_q3"],
         "raw_tag": "us-gaap:Revenues", "source": "companyfacts", "reconciled": True, "filed_at": "2024-10-31"},
    ]
    stored = calculated_provenance("FY - YTD9", operands)
    stored["period_calculation"] = True
    _quarter(db, company, "revenue", 120, 4, acc["annual"], source="derived", provenance=stored)
    _quarter(db, company, "operating_cash_flow", 10, 3, acc["unlisted"])
    _quarter(db, company, "operating_cash_flow", 30, 4, acc["elsewhere"])
    _quarter(db, company, "net_income", 15, 3, acc["offsite"])
    # Reported EPS read from an 8-K exhibit, stored with its receipt as the quarterly repair writes it.
    receipt = {**reported_provenance({"reconciled": True}), "source_sha256": "a" * 64,
               "source_url": _document(company.cik, acc["eps_8k"], "ex99-1.htm")}
    _quarter(db, company, "earnings_per_share", "1.25", 3, acc["eps_8k"], unit="USD/shares",
             source="reported_eps", form="8-K", raw_tag=None, provenance=receipt)
    db.flush()
    return acc


def test_the_multi_period_dataset_opens_each_cited_filings_document(dataset_db):
    db, company, other, prefix = dataset_db
    acc = _seed(db, company, other, prefix)

    statements = []
    engine = db.get_bind()

    def spy(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", spy)
    try:
        dataset = svc.build_dataset(db, company, "quarterly", "2024Q3", "2024Q4")
    finally:
        event.remove(engine, "before_cursor_execute", spy)
    assert len([statement for statement in statements if "FROM filings" in statement]) == 1

    revenue = _points(dataset, "revenue")
    later = _document(company.cik, acc["later_q3"], "later-q3-10q.htm")
    annual_doc = _document(company.cik, acc["annual"], "annual-10k.htm")
    original = _document(company.cik, acc["original_q3"], "original-q3-10q.htm")
    assert revenue["2024Q3"]["source_url"] == revenue["2024Q3"]["provenance"]["source_url"] == later
    q4 = revenue["2024Q4"]
    assert q4["derived"] is True and q4["source_url"] is None
    assert [item["source_url"] for item in q4["provenance"]["inputs"]] == [annual_doc, original]
    # The comparison's operands carry the points' links, the calculated point's nested ones too.
    qoq = q4["qoq_provenance"]["inputs"]
    assert "source_url" not in qoq[0] and qoq[1]["source_url"] == later
    assert [item["source_url"] for item in qoq[0]["provenance"]["inputs"]] == [annual_doc, original]
    # No filing row, or only another company's: the folder, under this company's CIK.
    cash = _points(dataset, "operating_cash_flow")
    assert cash["2024Q3"]["source_url"] == build_sec_archive_url(company.cik, acc["unlisted"])
    assert cash["2024Q4"]["source_url"] == build_sec_archive_url(company.cik, acc["elsewhere"])
    # A row whose document is on another host lends nothing either, and a stored link stays.
    assert _points(dataset, "net_income")["2024Q3"]["source_url"] == build_sec_archive_url(company.cik, acc["offsite"])
    assert _points(dataset, "earnings_per_share")["2024Q3"]["source_url"] == _document(
        company.cik, acc["eps_8k"], "ex99-1.htm")

    index = svc.marker_index(dataset)
    marker = revenue["2024Q3"]["marker"]
    assert svc._point_citation(1, index[marker])["source_url"] == later
    assert _operand(marker, index[marker], 1, frozenset())["source_url"] == later
    cited = svc._point_citation(2, index[q4["marker"]])["provenance"]["inputs"]
    assert [item["source_url"] for item in cited] == [annual_doc, original]


def test_a_snapshot_reads_each_looked_up_link_as_its_folder(dataset_db):
    """A filing row that turns folder links into documents moves no snapshot, and the folder build hashes as main hashed it."""
    db, company, other, prefix = dataset_db
    acc = _seed(db, company, other, prefix)
    documents = svc.build_dataset(db, company, "quarterly", "2024Q3", "2024Q4")
    db.query(Filing).filter(Filing.company_id == company.id).delete()
    db.flush()
    folders = svc.build_dataset(db, company, "quarterly", "2024Q3", "2024Q4")
    links = [_points(dataset, "revenue")["2024Q3"]["source_url"] for dataset in (documents, folders)]
    assert links == [
        _document(company.cik, acc["later_q3"], "later-q3-10q.htm"), build_sec_archive_url(company.cik, acc["later_q3"]),
    ]
    assert documents["snapshot_id"] == folders["snapshot_id"] == svc.dataset_fingerprint(folders)
    # The folder build carries the links main gave, the EPS exhibit held with its receipt among them:
    # folding leaves it as it is, so its hash is main's raw hash of the same dataset.
    assert folder_links(folders) == folders


@pytest.mark.parametrize("holder", ["point", "provenance"])
def test_a_link_stored_with_its_receipt_is_hashed_as_stored(dataset_db, holder):
    """The EPS point's receipt sits on the provenance beside its link, the provenance's on its own
    mapping: another exhibit in the same folder moves the snapshot through either link alone."""
    db, company, other, prefix = dataset_db
    acc = _seed(db, company, other, prefix)
    dataset = svc.build_dataset(db, company, "quarterly", "2024Q3", "2024Q4")
    eps = _points(dataset, "earnings_per_share")["2024Q3"]
    (eps if holder == "point" else eps["provenance"])["source_url"] = _document(company.cik, acc["eps_8k"], "ex99-2.htm")
    assert svc.dataset_fingerprint(dataset) != dataset["snapshot_id"]

