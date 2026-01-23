import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Ideally, we should import app, get_db, Base from backend
# Since we are running from root, we need to adjust sys.path or use relative imports properly if configured
# Assuming PYTHONPATH includes backend/

from app.database import Base, get_db
from main import app
from app.models.contact import ContactSubmission
from app.config import settings

# Setup in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = lambda: Session(bind=engine)

# Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(setup_database):
    # Ensure a fresh session/transaction for each test if needed, 
    # but for simple tests, the overridden dependency usually handles it.
    # We might want to clear table data between tests.
    with TestClient(app) as c:
        yield c
    
    # Cleanup data
    db = TestingSessionLocal()
    db.query(ContactSubmission).delete()
    db.commit()
    db.close()

@pytest.fixture
def mock_send_email():
    with patch("app.routers.contact.send_email") as mock:
        yield mock

def test_contact_submission_success(client, mock_send_email):
    """
    Test a valid contact form submission.
    """
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "subject": "Test Subject",
        "message": "This is a valid test message with enough length."
    }
    response = client.post("/api/contact/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["email"] == payload["email"]
    assert data["status"] == "new"
    
    # Verify email was called
    assert mock_send_email.called
    assert mock_send_email.call_count >= 1 # User confirmation + Admin notification (maybe)

def test_contact_submission_missing_config_resilience(client, mock_send_email):
    """
    Test that the API returns 201 even if RESEND_FROM_EMAIL is missing/malformed.
    This verifies the robust error handling we added.
    """
    # Mock settings.RESEND_FROM_EMAIL to be None
    with patch.object(settings, 'RESEND_FROM_EMAIL', None):
        payload = {
            "name": "Config Test",
            "email": "config@example.com",
            "subject": "Config Test",
            "message": "Testing configuration resilience."
        }
        response = client.post("/api/contact/", json=payload)
        
        # Should still succeed (saved to DB), just failed to send email
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == payload["email"]

    # Mock settings.RESEND_FROM_EMAIL to be malformed
    with patch.object(settings, 'RESEND_FROM_EMAIL', "Malformed Email"):
        payload = {
            "name": "Config Test 2",
            "email": "config2@example.com",
            "subject": "Config Test 2",
            "message": "Testing configuration resilience."
        }
        response = client.post("/api/contact/", json=payload)
        assert response.status_code == 201

from app.routers.contact import _rate_limit_store

def test_contact_submission_rate_limit(client, mock_send_email):
    """
    Test rate limiting (3 requests per hour).
    """
    # Clear rate limit store to ensure fresh start
    _rate_limit_store.clear()

    payload = {
        "name": "Spam User",
        "email": "spam@example.com",
        "subject": "Spam",
        "message": "This is a spam message for rate limiting."
    }
    
    # Send 3 requests (allowed)
    for i in range(3):
        response = client.post("/api/contact/", json=payload)
        assert response.status_code == 201, f"Request {i+1} failed"

    # Send 4th request (should be blocked)
    response = client.post("/api/contact/", json=payload)
    assert response.status_code == 429
    assert "Too many requests" in response.text
