"""The peers fixture is what the endpoint answers, and the frontend's client reads only what it serves (E251).

``frontend/tests/unit/fixtures/peers-cohorts.json`` feeds the company page's Sector peers panel and its gates: the
panel's unit specs, the engine's sweeps over its charts and the browser gate that mounts it. Production answers no
cohort until the SIC backfill runs, so these fixture answers are the only cohorts the panel is built and checked on;
a fixture the service would never answer would gate a panel production never draws.

1. Each case, seeded into a database of its own as ``test_peers_service.py`` seeds one (a company per entry, in the
   case's SIC code, and its latest annual fact for the case's concept, in the case's unit), answers exactly the case's
   response when ``peers_service.get_peers`` is asked for the case's ticker and the metric its request named, read
   through the endpoint's response model as the wire carries it: the order, ranks, percentiles, ``peer_count``,
   ``unit``, ``concept``, the subject (synthesised where it holds no fact) and each entry's provenance. A stored row
   is chosen for each entry from the provenance the fixture gives it (reported, a legacy calculation, a withheld
   derived EPS); a provenance this cannot seed fails. A source link comes from the entry's CIK and accession, so
   production's entries keep theirs, and a synthetic entry's accession is no SEC accession, so it gets none.
2. The bank case asks for revenue and answers net interest income: the substitution in ``peers_service.py`` (a
   subject with no revenue fact and a net interest income one) has its first test here, and a revenue fact added for
   the subject turns it back.
3. No fixture case, response or entry carries a key ``PeerComparisonResponse`` or ``PeerEntry`` does not define (the
   retired client's phantom ``PeerEntry.source_url``, which the endpoint never sent).
4. The client's types (``frontend/features/peers/api/peers-api.ts``) name the schema's fields and only those:
   ``PeerEntry`` all of them, ``PeerComparisonResponse`` all but ``sic``, which no copy prints (E251).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Company
from app.models.financial_fact import FinancialFact
from app.schemas.peers import PeerComparisonResponse, PeerEntry
from app.services import peers_service
from app.services.fact_provenance import EPS_CONCEPTS, METRIC_FORMULAS

REPO = Path(__file__).resolve().parents[3]
FIXTURE = json.loads((REPO / "frontend" / "tests" / "unit" / "fixtures" / "peers-cohorts.json").read_text(encoding="utf-8"))
CLIENT = REPO / "frontend" / "features" / "peers" / "api" / "peers-api.ts"
CASES = FIXTURE["cases"]
CASE_KEYS = {"case", "metric", "response"}
# The one schema field the client leaves unread: no copy prints the SIC code (E251's PR 2).
UNREAD_BY_THE_CLIENT = {"sic"}
SOURCE_URL = re.compile(r"^https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/$")


def _stored_row(concept: str, provenance: dict[str, Any]) -> dict[str, Any]:
    """The stored fact that projects to an entry's provenance (fact_provenance.provenance_for_fact): a legacy row,
    with no stored lineage, as production's answers carry."""
    kind = (provenance["method"], provenance["validation"], tuple(provenance["reasons"]))
    if kind == ("reported", "passed", ()):
        return {"source": "edgar_xbrl", "raw_tag": f"us-gaap:{concept}", "reconciled": True}
    if kind == ("calculated", "needs_review", ("legacy_calculation",)) and concept in METRIC_FORMULAS:
        return {"source": "edgar_xbrl", "raw_tag": None, "reconciled": False}
    if kind == ("calculated", "unavailable", ("unsupported_eps_calculation",)) and concept in EPS_CONCEPTS:
        return {"source": "derived", "raw_tag": None, "reconciled": False}
    raise AssertionError(f"the contract cannot seed a {concept} fact whose provenance is {kind}")


def _seed(db, response: dict[str, Any]) -> None:
    """A company for each entry (the subject's own row where it holds no fact) and each entry's latest annual fact."""
    entries = list(response["peers"])
    if not any(entry["is_subject"] for entry in entries):
        entries.append({**response["subject"], "no_fact": True})
    for i, entry in enumerate(entries):
        link = SOURCE_URL.match((entry.get("provenance") or {}).get("source_url") or "")
        # A synthetic company's CIK is its place; its accession is no SEC accession, so no source link is built.
        cik, accession = (link.group(1), link.group(2)) if link else (str(900_000 + i), f"synthetic-{i}")
        company = Company(cik=cik, ticker=entry["ticker"], name=entry["company_name"], sic=response["sic"])
        db.add(company)
        db.flush()
        if entry.get("no_fact"):
            continue
        db.add(FinancialFact(
            company_id=company.id, concept=response["concept"], unit=response["unit"],
            period_end=date.fromisoformat(entry["period_end"]), fiscal_year=entry["fiscal_year"], fiscal_period="FY",
            # A withheld entry's stored value: the service withholds it, whatever it is.
            value=entry["value"] if entry["value"] is not None else 1.0,
            form="10-K", accession=accession, provenance=None, is_latest=True,
            **_stored_row(response["concept"], entry["provenance"]),
        ))
    db.commit()


@pytest.fixture
def session():
    """A database of the case's own: two companies may answer one ticker (Company.ticker is not unique), and JPM is
    the subject of two cases."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Company.__table__.create(engine)
    FinancialFact.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        yield db
    engine.dispose()


def _answer(db, case: dict[str, Any]) -> dict[str, Any]:
    result = peers_service.get_peers(db, case["response"]["ticker"], case["metric"])
    assert result is not None, "the subject is a known company"
    return PeerComparisonResponse.model_validate(result).model_dump(mode="json")


def test_the_fixture_holds_the_panels_cases():
    # The panel's gates read these by name; a renamed or dropped case fails here before it fails there.
    assert {"pair", "spread", "near-equal", "net margin", "production single", "no facts", "withheld peer",
            "withheld subject", "pair plus withheld", "cap", "cap, subject fifth", "bank"} <= set(CASES)


@pytest.mark.parametrize("name", list(CASES))
def test_each_case_is_what_the_service_answers(session, name):
    case = CASES[name]
    _seed(session, case["response"])
    assert _answer(session, case) == case["response"]


def test_a_bank_asked_for_revenue_answers_net_interest_income(session):
    case = CASES["bank"]
    assert (case["metric"], case["response"]["concept"]) == ("revenue", "net_interest_income")
    _seed(session, case["response"])
    assert _answer(session, case)["concept"] == "net_interest_income"
    # The substitution is the subject's: once it holds a revenue fact, revenue is what it ranks on.
    subject = session.query(Company).filter(Company.ticker == case["response"]["ticker"]).one()
    session.add(FinancialFact(
        company_id=subject.id, concept="revenue", unit="USD", period_end=date(2025, 12, 31), fiscal_year=2025,
        fiscal_period="FY", value=40.0e9, form="10-K", accession="synthetic-revenue", source="edgar_xbrl",
        raw_tag="us-gaap:Revenues", reconciled=True, is_latest=True,
    ))
    session.commit()
    assert _answer(session, case)["concept"] == "revenue"


@pytest.mark.parametrize("name", list(CASES))
def test_no_case_carries_a_key_the_endpoint_does_not_serve(name):
    case = CASES[name]
    assert set(case) <= CASE_KEYS, f"{name}: a case holds {sorted(set(case) - CASE_KEYS)}"
    response = case["response"]
    extra = set(response) - set(PeerComparisonResponse.model_fields)
    assert not extra, f"{name}: PeerComparisonResponse defines no {sorted(extra)}"
    for entry in [response["subject"], *response["peers"]]:
        extra = set(entry) - set(PeerEntry.model_fields)
        assert not extra, f"{name}, {entry['ticker']}: PeerEntry defines no {sorted(extra)}"


def _client_fields(interface: str) -> set[str]:
    """The field names of one `export interface` in the client, a field a line, its doc comments skipped."""
    source = CLIENT.read_text(encoding="utf-8")
    match = re.search(rf"export interface {interface} \{{\n(.*?)\n\}}", source, re.S)
    assert match, f"{CLIENT.name} declares `export interface {interface}`"
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", match.group(1), flags=re.S)
    assert "{" not in body, f"{interface}: a nested type this reader cannot follow"
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    fields = [re.match(r"^(\w+)\??\s*:", line) for line in lines]
    assert all(fields), f"{interface}: a line this reader cannot read: {[line for line, f in zip(lines, fields) if not f]}"
    return {field.group(1) for field in fields}


def test_the_client_reads_what_the_endpoint_serves():
    assert _client_fields("PeerEntry") == set(PeerEntry.model_fields)
    assert _client_fields("PeerComparisonResponse") == set(PeerComparisonResponse.model_fields) - UNREAD_BY_THE_CLIENT
