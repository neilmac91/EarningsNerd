"""Saved-summary library routes: save, update notes, delete and list, end to end over HTTP.

Characterizes the response bodies, the 404 details and the per-user scoping, and reads the stored
rows back through a separate session so a write that never committed cannot pass. Nothing is
patched: the routes run against a real SQLite schema. The status route has its own spec
(``test_saved_summary_status.py``).
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.models import Company, Filing, SavedSummary, Summary, User
from app.routers.auth import get_current_user
from app.routers.saved_summaries import router

FILED = datetime(2026, 1, 2, tzinfo=timezone.utc)


@pytest.fixture
def library(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'library.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner, other = User(email="owner@example.test"), User(email="other@example.test")
        company = Company(cik="7", ticker="LIB", name="Library Co")
        db.add_all([owner, other, company])
        db.flush()
        summary_ids, filing_ids = [], []
        for i in range(3):
            filing = Filing(company_id=company.id, accession_number=f"library-{i}", filing_type="10-Q",
                            filing_date=FILED, sec_url="https://sec.example/", document_url="https://sec.example/doc")
            db.add(filing)
            db.flush()
            summary = Summary(filing_id=filing.id, business_overview=f"Overview {i}")
            db.add(summary)
            db.flush()
            filing_ids.append(filing.id)
            summary_ids.append(summary.id)
        others_row = SavedSummary(user_id=other.id, summary_id=summary_ids[1], notes="Other notes")
        db.add(others_row)
        db.commit()
        ctx = SimpleNamespace(engine=engine, owner_id=owner.id, other_id=other.id, company_id=company.id,
                              summary_ids=summary_ids, filing_ids=filing_ids, others_row_id=others_row.id)
    app = FastAPI()
    app.include_router(router, prefix="/api/saved-summaries")

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=ctx.owner_id)
    with TestClient(app) as client:
        ctx.client = client
        yield ctx
    engine.dispose()


def _rows(ctx) -> list[tuple[int, int, int, str | None]]:
    with Session(ctx.engine) as db:
        return [(r.id, r.user_id, r.summary_id, r.notes) for r in db.query(SavedSummary).order_by(SavedSummary.id)]


def test_save_unknown_summary_is_404_and_writes_nothing(library):
    before = _rows(library)
    response = library.client.post("/api/saved-summaries/", json={"summary_id": 999999, "notes": "x"})
    assert response.status_code == 404 and response.json() == {"detail": "Summary not found"}
    assert _rows(library) == before


def test_save_returns_the_library_row_and_resaving_only_touches_notes_when_given(library):
    summary_id = library.summary_ids[0]
    created = library.client.post("/api/saved-summaries/", json={"summary_id": summary_id, "notes": "First"})
    assert created.status_code == 200
    body = created.json()
    assert set(body) == {"id", "summary_id", "notes", "created_at", "summary", "filing", "company"}
    assert body["summary_id"] == summary_id and body["notes"] == "First"
    assert isinstance(body["created_at"], str) and body["created_at"]
    assert body["summary"] == {"id": summary_id, "filing_id": library.filing_ids[0], "business_overview": "Overview 0"}
    assert set(body["filing"]) == {"id", "filing_type", "filing_date", "period_end_date"}
    assert body["filing"]["id"] == library.filing_ids[0] and body["filing"]["filing_type"] == "10-Q"
    assert body["filing"]["filing_date"].startswith("2026-01-02T00:00:00")
    assert body["filing"]["period_end_date"] is None
    assert body["company"] == {"id": library.company_id, "ticker": "LIB", "name": "Library Co"}
    saved_id = body["id"]

    unchanged = library.client.post("/api/saved-summaries/", json={"summary_id": summary_id})
    assert unchanged.status_code == 200
    assert unchanged.json()["id"] == saved_id and unchanged.json()["notes"] == "First"

    renoted = library.client.post("/api/saved-summaries/", json={"summary_id": summary_id, "notes": "Second"})
    assert renoted.status_code == 200
    assert renoted.json()["id"] == saved_id and renoted.json()["notes"] == "Second"
    assert (saved_id, library.owner_id, summary_id, "Second") in _rows(library)
    assert len([r for r in _rows(library) if r[1] == library.owner_id]) == 1


def test_saving_a_summary_another_user_saved_creates_the_callers_own_row(library):
    summary_id = library.summary_ids[1]
    response = library.client.post("/api/saved-summaries/", json={"summary_id": summary_id})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] != library.others_row_id and body["notes"] is None
    rows = _rows(library)
    assert (library.others_row_id, library.other_id, summary_id, "Other notes") in rows
    assert (body["id"], library.owner_id, summary_id, None) in rows


def test_update_notes_persists_only_when_given_and_is_scoped_to_the_owner(library):
    saved_id = library.client.post("/api/saved-summaries/", json={"summary_id": library.summary_ids[0]}).json()["id"]

    edited = library.client.put(f"/api/saved-summaries/{saved_id}", params={"notes": "Edited"})
    assert edited.status_code == 200
    assert edited.json()["id"] == saved_id and edited.json()["notes"] == "Edited"
    assert edited.json()["company"] == {"id": library.company_id, "ticker": "LIB", "name": "Library Co"}

    untouched = library.client.put(f"/api/saved-summaries/{saved_id}")
    assert untouched.status_code == 200 and untouched.json()["notes"] == "Edited"
    assert (saved_id, library.owner_id, library.summary_ids[0], "Edited") in _rows(library)

    for missing in (library.others_row_id, 999999):
        response = library.client.put(f"/api/saved-summaries/{missing}", params={"notes": "Hijack"})
        assert response.status_code == 404 and response.json() == {"detail": "Saved summary not found"}
    assert (library.others_row_id, library.other_id, library.summary_ids[1], "Other notes") in _rows(library)


def test_delete_is_scoped_to_the_owner_and_removes_the_row(library):
    response = library.client.delete(f"/api/saved-summaries/{library.others_row_id}")
    assert response.status_code == 404 and response.json() == {"detail": "Saved summary not found"}
    assert any(r[0] == library.others_row_id for r in _rows(library))

    saved_id = library.client.post("/api/saved-summaries/", json={"summary_id": library.summary_ids[0]}).json()["id"]
    deleted = library.client.delete(f"/api/saved-summaries/{saved_id}")
    assert deleted.status_code == 200 and deleted.json() == {"status": "success"}
    assert all(r[0] != saved_id for r in _rows(library))

    again = library.client.delete(f"/api/saved-summaries/{saved_id}")
    assert again.status_code == 404 and again.json() == {"detail": "Saved summary not found"}


def test_list_returns_only_the_callers_rows_newest_first(library):
    with Session(library.engine) as db:
        db.add_all([
            SavedSummary(user_id=library.owner_id, summary_id=library.summary_ids[0], notes="older",
                         created_at=FILED + timedelta(days=1)),
            SavedSummary(user_id=library.owner_id, summary_id=library.summary_ids[2], notes="newer",
                         created_at=FILED + timedelta(days=2)),
        ])
        db.commit()
    response = library.client.get("/api/saved-summaries/")
    assert response.status_code == 200
    rows = response.json()
    assert [(r["summary_id"], r["notes"]) for r in rows] == [
        (library.summary_ids[2], "newer"), (library.summary_ids[0], "older"),
    ]
    assert rows[0]["filing"]["id"] == library.filing_ids[2]
    assert rows[0]["summary"]["business_overview"] == "Overview 2"
    assert rows[0]["created_at"].startswith("2026-01-04T00:00:00")
