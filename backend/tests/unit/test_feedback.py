"""Unit tests for the beta-feedback endpoint (POST /api/feedback/).

Uses a per-test in-memory SQLite DB (real writes — the endpoint persists a row and echoes its id/
status), with the auth + db dependencies overridden. The Stripe-style MagicMock db won't work here
because the response is built from the refreshed ORM row.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.database import Base, get_db
from app.routers import feedback as feedback_router
from app.routers.auth import get_current_user
from app.models.feedback import Feedback


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def client(session_factory):
    feedback_router._rate_store.clear()

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, email="beta@example.com")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_submit_feedback_persists_row(client, session_factory):
    resp = client.post(
        "/api/feedback/",
        json={"type": "bug", "message": "Charts fail to load on AAPL", "page_url": "/company/AAPL"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "bug"
    assert body["status"] == "new"
    assert isinstance(body["id"], int)

    with session_factory() as s:
        rows = s.query(Feedback).all()
        assert len(rows) == 1
        assert rows[0].user_id == 1
        assert rows[0].page_url == "/company/AAPL"
        assert rows[0].ip_address  # IP is stored hashed (non-empty), never plaintext


def test_default_type_is_general(client, session_factory):
    resp = client.post("/api/feedback/", json={"message": "Would love a dark-mode toggle here"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["type"] == "general"


def test_short_message_rejected(client):
    resp = client.post("/api/feedback/", json={"type": "general", "message": "hi"})
    assert resp.status_code == 422


def test_invalid_type_rejected(client):
    resp = client.post("/api/feedback/", json={"type": "spam", "message": "this is long enough"})
    assert resp.status_code == 422


def test_per_user_rate_limit(client):
    for _ in range(feedback_router._RATE_LIMIT_REQUESTS):
        assert client.post("/api/feedback/", json={"message": "still within the limit"}).status_code == 201
    blocked = client.post("/api/feedback/", json={"message": "one too many requests now"})
    assert blocked.status_code == 429
