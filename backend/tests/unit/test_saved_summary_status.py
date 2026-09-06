"""Selected-summary status is authenticated, user-scoped and independent of library payloads."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.models import Company, Filing, SavedSummary, Summary, User
from app.routers.auth import get_current_user
from app.routers.saved_summaries import router
from app.utils.datetimes import utcnow


@pytest.fixture
def library(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'saved.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner, other = User(email="owner@example.test"), User(email="other@example.test")
        company = Company(cik="1", ticker="TEST", name="Test")
        db.add_all([owner, other, company])
        db.flush()
        ids = []
        for i in range(3):
            filing = Filing(company_id=company.id, accession_number=f"saved-{i}", filing_type="10-K",
                            filing_date=utcnow(), sec_url="https://sec.example/", document_url="https://sec.example/doc")
            db.add(filing)
            db.flush()
            summary = Summary(filing_id=filing.id, business_overview="Private library payload " * 1000)
            db.add(summary)
            db.flush()
            ids.append(summary.id)
        db.add_all([SavedSummary(user_id=owner.id, summary_id=ids[0], notes="Owner notes"),
                    SavedSummary(user_id=other.id, summary_id=ids[1], notes="Other notes")])
        db.commit()
        owner_id, other_id = owner.id, other.id
    app = FastAPI()
    app.include_router(router, prefix="/api/saved-summaries")

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=owner_id)
    with TestClient(app) as client:
        yield client, app, engine, ids, other_id
    engine.dispose()


def test_status_is_scoped_to_authenticated_user_and_missing_summary_is_404(library):
    client, app, _, ids, other_id = library
    assert client.get(f"/api/saved-summaries/status/{ids[0]}").json() == {"is_saved": True}
    assert client.get(f"/api/saved-summaries/status/{ids[1]}").json() == {"is_saved": False}
    assert client.get(f"/api/saved-summaries/status/{ids[2]}").json() == {"is_saved": False}
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=other_id)
    assert client.get(f"/api/saved-summaries/status/{ids[0]}").json() == {"is_saved": False}
    assert client.get(f"/api/saved-summaries/status/{ids[1]}").json() == {"is_saved": True}
    response = client.get("/api/saved-summaries/status/999999")
    assert response.status_code == 404 and response.json() == {"detail": "Summary not found"}
    app.dependency_overrides.pop(get_current_user)
    assert client.get(f"/api/saved-summaries/status/{ids[0]}").status_code == 401


def test_status_never_materializes_library_entities_and_library_contract_stays_available(library):
    client, _, _, ids, _ = library

    def forbidden_load(*_):
        raise AssertionError("Status loaded a full library entity")

    models = (SavedSummary, Summary, Filing, Company)
    for model in models:
        event.listen(model, "load", forbidden_load)
    try:
        response = client.get(f"/api/saved-summaries/status/{ids[0]}")
        assert response.status_code == 200 and response.json() == {"is_saved": True}
    finally:
        for model in models:
            event.remove(model, "load", forbidden_load)
    rows = client.get("/api/saved-summaries/").json()
    assert len(rows) == 1 and rows[0]["summary_id"] == ids[0]
    assert rows[0]["notes"] == "Owner notes"
    assert rows[0]["summary"]["business_overview"].startswith("Private library payload")
