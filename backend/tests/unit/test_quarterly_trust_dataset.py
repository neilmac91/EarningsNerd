"""Consumer regressions for quarterly withholding, comparison windows and snapshots.

These are synthetic contract fixtures, not evidence of real-issuer coverage.
"""

import uuid
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models import Company, FinancialFact
from app.schemas.fundamentals import FundamentalPoint
from app.schemas.peers import PeerEntry
from app.services import peers_service
from app.services import trend_analysis_service as svc
from app.services.fact_provenance import calculated_provenance
from app.utils.sec_urls import build_sec_archive_url


@pytest.fixture
def dataset_db():
    """Keep this company's rows inside one rollback-only transaction."""
    with SessionLocal() as db:
        token = uuid.uuid4().hex
        company = Company(
            cik=str(int(token[:12], 16)), ticker=f"TRUST{token[:8]}", name="Synthetic trust fixture",
        )
        db.add(company)
        db.flush()
        yield db, company
        db.rollback()


def _quarter(db, company, concept, value, year, quarter, **changes):
    months = {1: (1, 3, 31), 2: (4, 6, 30), 3: (7, 9, 30), 4: (10, 12, 31)}
    start_month, end_month, end_day = months[quarter]
    values = {
        "company_id": company.id, "concept": concept, "value": Decimal(str(value)),
        "unit": "USD/shares" if concept in {"eps_basic", "eps_diluted", "earnings_per_share"} else "USD",
        "period_start": date(year, start_month, 1), "period_end": date(year, end_month, end_day),
        "fiscal_year": year, "fiscal_period": f"Q{quarter}", "form": "10-Q",
        "accession": f"0001326801-{year % 100:02d}-{quarter:06d}",
        "raw_tag": f"us-gaap:{concept}", "source": "companyfacts", "reconciled": True,
        "is_latest": True, **changes,
    }
    row = FinancialFact(**values)
    db.add(row)
    db.flush()
    return row


def _points(dataset, concept):
    series = next(item for item in dataset["series"] if item["concept"] == concept)
    return {point["period"]: point for point in series["points"]}


@pytest.mark.parametrize("middle_axis_exists", [False, True])
def test_qoq_does_not_jump_a_missing_quarter_or_missing_metric(dataset_db, middle_axis_exists):
    db, company = dataset_db
    _quarter(db, company, "operating_cash_flow", 10, 2024, 1)
    _quarter(db, company, "operating_cash_flow", 30, 2024, 3)
    if middle_axis_exists:
        _quarter(db, company, "revenue", 100, 2024, 2)
    dataset = svc.build_dataset(db, company, "quarterly", "2024Q1", "2024Q3")
    latest = _points(dataset, "operating_cash_flow")["2024Q3"]
    assert latest["qoq"] is None
    assert latest["qoq_reconciled"] is None
    assert "qoq_provenance" not in latest
    catalogue = svc.build_observation_catalogue(dataset)
    assert not any("QoQ +200" in observation.markdown for observation in catalogue)
    assert svc.marker_index(dataset)[latest["marker"]]["qoq"] is None


def test_qoq_crosses_the_year_boundary_only_from_the_actual_prior_quarter(dataset_db):
    db, company = dataset_db
    _quarter(db, company, "revenue", 100, 2023, 4)
    _quarter(db, company, "revenue", 120, 2024, 1)
    dataset = svc.build_dataset(db, company, "quarterly", "2023Q4", "2024Q1")
    latest = _points(dataset, "revenue")["2024Q1"]
    assert latest["qoq"] == pytest.approx(0.2)
    assert latest["qoq_reconciled"] is True
    assert [item["period_end"] for item in latest["qoq_provenance"]["inputs"]] == [
        "2024-03-31", "2023-12-31",
    ]


def _calculated_q4(db, company):
    annual = {
        "concept": "revenue", "value": 420, "unit": "USD",
        "period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31),
        "accession": "0001326801-25-000010", "raw_tag": "us-gaap:Revenues",
        "source": "companyfacts", "reconciled": True, "filed_at": "2025-01-30",
    }
    prior = {
        **annual, "value": 300, "period_end": date(2024, 9, 30),
        "accession": "0001326801-24-000091", "filed_at": "2024-10-31",
    }
    provenance = calculated_provenance("FY - YTD9", [annual, prior])
    provenance["period_calculation"] = True
    return _quarter(db, company, "revenue", 120, 2024, 4, source="derived", provenance=provenance)


def test_validated_q4_keeps_calculation_identity_and_real_operand_sources(dataset_db):
    db, company = dataset_db
    _quarter(db, company, "revenue", 100, 2024, 3)
    _calculated_q4(db, company)
    dataset = svc.build_dataset(db, company, "quarterly", "2024Q3", "2024Q4")
    point = _points(dataset, "revenue")["2024Q4"]
    assert point["value"] == 120
    assert point["derived"] is True
    assert point["reconciled"] is True
    assert point["qoq"] == pytest.approx(0.2)
    assert point["qoq_reconciled"] is True
    citation = svc._point_citation(1, svc.marker_index(dataset)[point["marker"]])
    assert citation["section_ref"] == "Calculated · FY - YTD9"
    assert citation["provenance"]["validation"] == "passed"
    operands = citation["provenance"]["inputs"]
    assert operands[0]["source_url"] == build_sec_archive_url(company.cik, "0001326801-25-000010")
    assert operands[1]["source_url"] == build_sec_archive_url(company.cik, "0001326801-24-000091")


@pytest.mark.parametrize("concept", ["earnings_per_share", "eps_diluted"])
def test_legacy_eps_is_withheld_across_dataset_peer_and_nullable_schema(dataset_db, concept):
    db, company = dataset_db
    legacy = _quarter(db, company, concept, 7.95, 2024, 4, source="derived", reconciled=False)
    dataset = svc.build_dataset(db, company, "quarterly", "2024Q4", "2024Q4")
    point = _points(dataset, concept)["2024Q4"]
    assert point["value"] is None
    assert "marker" not in point
    assert not svc.marker_index(dataset)
    assert point["provenance"]["reasons"] == ["unsupported_eps_calculation"]
    assert FundamentalPoint.model_validate(point).value is None
    peer = PeerEntry.model_validate(peers_service._entry(company, legacy, is_subject=True))
    assert peer.value is None and peer.rank is None
    assert peer.provenance["validation"] == "unavailable"
    catalogue = svc.build_observation_catalogue(dataset)
    context = "\n".join(observation.markdown for observation in catalogue)
    assert "7.95" not in context  # Withheld EPS cannot become a numeric model observation.
    assert "not reported" not in context.lower()
    assert "not available in this selected dataset" in context.lower()


def test_narrative_citation_preserves_review_status_instead_of_asserting_a_clean_fact(dataset_db):
    db, company = dataset_db
    _quarter(db, company, "revenue", 120, 2024, 4, source="derived", reconciled=False)
    dataset = svc.build_dataset(db, company, "quarterly", "2024Q4", "2024Q4")
    point = _points(dataset, "revenue")["2024Q4"]
    catalogue = svc.build_observation_catalogue(dataset)
    assert any(f"[{point['marker']}]" in observation.markdown for observation in catalogue)
    marker = svc.marker_index(dataset)[point["marker"]]
    assert marker["provenance"]["validation"] == "needs_review"
    assert marker["provenance"]["reasons"] == ["legacy_calculation"]
    citation = svc._point_citation(1, marker)
    # Citation resolution and financial validation are separate contracts.
    assert citation["reconciled"] is False
    assert citation["provenance"]["validation"] == "needs_review"
    assert citation["provenance"]["reasons"] == ["legacy_calculation"]


def test_snapshot_ignores_fetch_metadata_but_tracks_values_and_source_lineage(dataset_db):
    db, company = dataset_db
    company.facts_synced_at = datetime(2026, 10, 10, 16, tzinfo=timezone.utc)
    _calculated_q4(db, company)
    dataset = svc.build_dataset(db, company, "quarterly", "2024Q4", "2024Q4")
    original = svc.dataset_fingerprint(dataset)
    assert dataset["snapshot_id"] == original
    assert dataset["data_as_of"] == "2026-10-10T16:00:00Z"
    refreshed = deepcopy(dataset)
    refreshed.update(snapshot_id="f" * 64, data_as_of="2026-10-10T16:00:00+00:00")
    assert svc.dataset_fingerprint(refreshed) == original
    corrected_value = deepcopy(dataset)
    _points(corrected_value, "revenue")["2024Q4"]["value"] = 121
    assert svc.dataset_fingerprint(corrected_value) != original
    corrected_source = deepcopy(dataset)
    operand = _points(corrected_source, "revenue")["2024Q4"]["provenance"]["inputs"][0]
    operand["accession"] = "0001326801-25-000011"
    operand["source_url"] = build_sec_archive_url(company.cik, operand["accession"])
    assert svc.dataset_fingerprint(corrected_source) != original
    revised_quality = deepcopy(dataset)
    _points(revised_quality, "revenue")["2024Q4"]["provenance"]["validation"] = "needs_review"
    assert svc.dataset_fingerprint(revised_quality) != original
