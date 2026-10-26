"""E149: a fact's source link opens its filing's primary document, not the accession folder.

``fact_provenance`` links each reported value and each calculation operand that stores no link.
Given a lookup (dashless accession to the filing row's ``document_url``) it takes that filing's
document when it is an SEC archive URL inside the accession's folder; any other accession keeps
its folder (``build_sec_archive_url``), and a call without the lookup links every one to its
folder, as before. The Multi-Period dataset builds the lookup with one read of the company's
filing rows (``trend_analysis/source_documents.py``), so its points, their operands, their
comparisons and the narrative's citations open the document. Its snapshot fingerprint hashes each
looked-up link as its folder, so a filing row that lands moves no snapshot; a link stored with its
receipt is hashed as stored. A saved narrative re-served while its snapshot holds answers with the
rebuilt dataset's links (``current_links``), each inside the folder it saved, and its row stays as saved.
Its PDF renders a copy of the row that takes the same links (``cached_analysis_export``).

Synthetic fixtures, not real-issuer coverage.
"""

import json
import re
import uuid
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.database import SessionLocal
from app.models import Company, Filing, FinancialFact, TrendAnalysis
from app.services import trend_analysis_service as svc
from app.services.fact_provenance import calculated_provenance, provenance_for_fact, reported_provenance
from app.services.trend_analysis.presentation import _operand, cached_analysis_export
from app.services.trend_analysis.source_documents import current_links, folder_links
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
    # Filing rows: the 10-K dashed, the later 10-Q dashless, another company's row for `elsewhere`
    # whose document sits under this company's folder (so only the read's company filter keeps it
    # out), and a row whose document is on another host.
    _filing(db, company, acc["annual"], "annual-10k.htm", "10-K")
    _filing(db, company, acc["original_q3"], "original-q3-10q.htm")
    _filing(db, company, normalize_accession(acc["later_q3"]), "later-q3-10q.htm")
    _filing(db, other, acc["elsewhere"], "", "10-K",
            document_url=_document(company.cik, acc["elsewhere"], "another-filers-10k.htm"))
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
    # No filing row, or only another company's (even with a document in this folder): the folder.
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


def test_a_re_served_link_only_moves_inside_its_accession_folder():
    """An item takes its point's link where the snapshot reads the two alike: never another accession's,
    a link stored with its receipt, or a marker the dataset no longer holds. The saved items are untouched."""
    folder, document = build_sec_archive_url(CIK, ANNUAL), _document(CIK, ANNUAL, "annual-10k.htm")
    receipt = {"source_sha256": "a" * 64, "source_url": _document(CIK, ANNUAL, "ex99-1.htm")}
    index = {
        "F1": {"source_url": document},
        "F2": {"provenance": {"source_url": document}},  # The citations' reading: the point's, else its provenance's.
        "F3": {"source_url": build_sec_archive_url(CIK, NINE_MONTHS)},
        "F4": {"source_url": _document(CIK, ANNUAL, "ex99-2.htm"), "provenance": receipt},  # The saved receipt, another exhibit.
    }
    saved = [
        {"marker": "F1", "source_url": folder}, {"marker": "F2", "source_url": folder},
        {"marker": "F3", "source_url": folder}, {"marker": "F4", "source_url": receipt["source_url"], "provenance": receipt},
        {"marker": "F9", "source_url": folder}, {"source_url": folder},
    ]
    before = deepcopy(saved)
    links = [item["source_url"] for item in current_links(saved, index)]
    assert links == [document, document, folder, receipt["source_url"], folder, folder]
    assert saved == before


def test_a_re_served_items_lineage_moves_with_its_links():
    """A calculated citation's operands are linked on its provenance copy, which the PDF lists: it takes the
    point's where the snapshot reads the two alike, and keeps its own when anything else differs."""
    folder, document = build_sec_archive_url(CIK, ANNUAL), _document(CIK, ANNUAL, "annual-10k.htm")

    def lineage(link, validation="passed"):
        return {"method": "calculated", "validation": validation, "inputs": [{"accession": ANNUAL, "source_url": link}]}

    index = {"F1": {"provenance": lineage(document)}, "F2": {"provenance": lineage(document, "needs_review")}}
    saved = [{"marker": marker, "source_url": None, "provenance": lineage(folder)} for marker in ("F1", "F2")]
    moved = current_links(saved, index)
    assert moved[0]["provenance"] == lineage(document) and moved[1] is saved[1]


def test_a_pdf_copy_takes_the_rebuilt_series_only_where_the_snapshot_reads_them_alike():
    """The PDF's copy of a saved row takes the rebuilt series, and its citations their links, inside the
    folders it saved, and keeps the saved snapshot's other keys; a link in another accession's folder
    keeps the saved series whole. The saved row is untouched."""
    folder, document = build_sec_archive_url(CIK, ANNUAL), _document(CIK, ANNUAL, "annual-10k.htm")

    def dataset(link, as_of):
        point = {"period": "FY2024", "value": 1.0, "marker": "F1", "source_url": link}
        series = {"concept": "revenue", "label": "Revenue", "unit": "USD", "percent": False, "points": [point]}
        return {"snapshot_id": "a" * 64, "data_as_of": as_of, "series": [series]}

    saved = SimpleNamespace(id=7, mode="annual", dataset_json=dataset(folder, "2026-01-02T00:00:00Z"),
                            citations_json=[{"marker": "F1", "source_url": folder}])
    before = deepcopy(vars(saved))
    moved = cached_analysis_export(dataset(document, "2026-10-22T00:00:00Z"), saved)
    assert (moved.id, moved.mode, moved.dataset_json["data_as_of"]) == (7, "annual", "2026-01-02T00:00:00Z")
    assert [moved.dataset_json["series"][0]["points"][0]["source_url"], moved.citations_json[0]["source_url"]] == [document] * 2
    kept = cached_analysis_export(dataset(build_sec_archive_url(CIK, NINE_MONTHS), "2026-10-22T00:00:00Z"), saved)
    assert [kept.dataset_json, kept.citations_json] == [saved.dataset_json, saved.citations_json]
    assert vars(saved) == before


@pytest.fixture
def saved_history():
    """A company of its own with three annual 10-Ks' facts and no filing rows, committed for the
    narrative stream's own sessions; the rows the test adds go with it afterwards."""
    token = uuid.uuid4().hex
    prefix = f"{int(token[12:20], 16) % 9_000_000_000 + 1_000_000_000}"
    ten_k = {year: f"{prefix}-{year - 1999}-000010" for year in (2021, 2022, 2023)}
    with SessionLocal() as db:
        company = Company(cik=str(int(token[:12], 16)), ticker=f"SAVE{token[:8]}", name="Synthetic saved analysis")
        db.add(company)
        db.flush()
        # Long-term debt grows by more than half across the window: a red flag with its evidence operands.
        for year, values in {2021: (1000, 100, 100), 2022: (1200, 130, 180), 2023: (1500, 180, 250)}.items():
            for concept, value in zip(("revenue", "net_income", "long_term_debt"), values):
                db.add(FinancialFact(
                    company_id=company.id, concept=concept, value=Decimal(value), unit="USD",
                    period_start=None if concept == "long_term_debt" else date(year, 1, 1),
                    period_end=date(year, 12, 31), fiscal_year=year, fiscal_period="FY", form="10-K",
                    accession=ten_k[year], raw_tag=f"us-gaap:{concept}", source="companyfacts",
                    reconciled=True, is_latest=True,
                ))
        db.commit()
        company_id, cik = company.id, company.cik
    yield company_id, cik, ten_k
    with SessionLocal() as db:
        for model in (TrendAnalysis, Filing, FinancialFact):
            db.query(model).filter(model.company_id == company_id).delete()
        db.query(Company).filter(Company.id == company_id).delete()
        db.commit()


@pytest.mark.asyncio
async def test_a_re_served_narrative_opens_the_documents_its_saved_folders_name(saved_history, monkeypatch):
    """A narrative saved with folder links, as main saved it or before its filing rows landed, re-serves
    while its snapshot holds. Its citations and red-flag evidence open the documents the rebuilt dataset
    links and a folder no row names stays; the saved row, its counts and the fidelity scan are as they were."""
    from app.services import openai_service as oa

    company_id, cik, ten_k = saved_history
    calls = []

    async def narrate(reply):
        async def fake(messages, **kwargs):
            calls.append(messages)
            yield reply

        monkeypatch.setattr(oa.openai_service, "stream_chat", fake)
        return [event async for event in svc.stream_trend_narrative(
            company_id=company_id, mode="annual", start_period="FY2021", end_period="FY2023",
        )][-1]

    def links(completion):
        evidence = completion["narrative_presentation"]["evidence"]
        return ({item["marker"]: item["source_url"] for item in completion["citations"]},
                {item["marker"]: item["source_url"] for entry in evidence for item in entry["operands"]})

    saved = await narrate(json.dumps({key: [] for key, _ in svc.ANALYSIS_SECTIONS}))
    with SessionLocal() as db:  # The FY2022 and FY2023 10-K rows land after the narrative was saved.
        company = db.get(Company, company_id)
        for year in (2022, 2023):
            _filing(db, company, ten_k[year], f"fy{year}-10k.htm", "10-K")
        db.commit()
        row = db.query(TrendAnalysis).filter(TrendAnalysis.company_id == company_id).one()
        stored = deepcopy([row.citations_json, row.dataset_json])
    served = await narrate("MUST NOT RUN")

    assert served["cached"] is True and len(calls) == 1  # The generation's one call; the re-serve makes none.
    same = ("snapshot_id", "narrative", "grounded", "unverified", "mismatched")
    assert [served[key] for key in same] == [saved[key] for key in same]
    folders = {year: build_sec_archive_url(cik, accession) for year, accession in ten_k.items()}
    opened = {folders[year]: folders[year] + f"fy{year}-10k.htm" for year in (2022, 2023)}
    (saved_citations, saved_evidence), (served_citations, served_evidence) = links(saved), links(served)
    assert set(folders.values()) <= set(saved_citations.values()) and folders[2023] in saved_evidence.values()
    assert served_citations == {marker: opened.get(url, url) for marker, url in saved_citations.items()}
    assert served_evidence == {marker: opened.get(url, url) for marker, url in saved_evidence.items()}
    with SessionLocal() as db:
        row = db.query(TrendAnalysis).filter(TrendAnalysis.company_id == company_id).one()
        assert [row.citations_json, row.dataset_json] == stored


@pytest.mark.asyncio
async def test_a_saved_analysis_pdf_opens_the_documents_its_saved_folders_name(saved_history, monkeypatch):
    """The PDF of a narrative saved with folder links, its 10-K rows landed since: the export's checks pass,
    and each link it renders (the citations', the methods' points' and their operands') opens the document
    the rebuilt dataset links in that folder. FY2021's folder stays, nothing else in the PDF changes, and
    the saved row is as it was."""
    from datetime import timedelta
    from itertools import count

    from app.routers import analysis as router
    from app.services import entitlements
    from app.services import export_service as export_module
    from app.services import openai_service as oa
    from app.services.export_service import export_service

    company_id, cik, ten_k = saved_history
    # Each export reads a later minute, so the comparison below holds only if the mask covers the whole instant.
    minutes = count()
    monkeypatch.setattr(export_module, "utcnow", lambda: datetime(2026, 10, 26, 9, 59, tzinfo=timezone.utc) + timedelta(minutes=next(minutes)))

    async def selection(messages, **kwargs):
        yield json.dumps({key: [] for key, _ in svc.ANALYSIS_SECTIONS})

    monkeypatch.setattr(oa.openai_service, "stream_chat", selection)
    events = [event async for event in svc.stream_trend_narrative(
        company_id=company_id, mode="annual", start_period="FY2021", end_period="FY2023",
    )]
    assert events[-1]["type"] == "complete"
    with SessionLocal() as db:  # The FY2022 and FY2023 10-K rows land after the narrative was saved.
        company = db.get(Company, company_id)
        for year in (2022, 2023):
            _filing(db, company, ten_k[year], f"fy{year}-10k.htm", "10-K")
        db.commit()
        row = db.query(TrendAnalysis).filter(TrendAnalysis.company_id == company_id).one()
        analysis_id, stored = row.id, deepcopy([row.citations_json, row.dataset_json])
        saved_pdf = export_service.generate_analysis_pdf_html(row, company)

    pdfs = []

    async def render(analysis, company):
        pdfs.append(export_service.generate_analysis_pdf_html(analysis, company))
        return b"%PDF-test"

    monkeypatch.setattr(entitlements, "get_entitlements", lambda user: SimpleNamespace(can_export=True))
    monkeypatch.setattr(export_service, "export_analysis_pdf", render)
    response = await router.export_analysis_pdf(
        analysis_id, snapshot_id=stored[1]["snapshot_id"], current_user=SimpleNamespace(), db=SessionLocal(),
    )

    assert response.body == b"%PDF-test" and len(pdfs) == 1
    folders = {year: build_sec_archive_url(cik, accession) for year, accession in ten_k.items()}
    opened = {folders[year]: folders[year] + f"fy{year}-10k.htm" for year in (2022, 2023)}
    links = re.compile(r'<a href="([^"]+)">Source filing \d+</a>')
    saved_links = links.findall(saved_pdf)
    assert set(saved_links) == set(folders.values())  # The saved row links each 10-K's folder, and only those.
    assert links.findall(pdfs[0]) == [opened.get(url, url) for url in saved_links]
    restored, exported = pdfs[0], re.compile(r"Exported [^<]*")  # the whole instant, to its clause's end
    for folder, document in opened.items():
        restored = restored.replace(document, folder)
    assert exported.sub("", restored) == exported.sub("", saved_pdf)
    with SessionLocal() as db:
        row = db.get(TrendAnalysis, analysis_id)
        assert [row.citations_json, row.dataset_json] == stored
