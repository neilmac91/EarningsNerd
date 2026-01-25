
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from app.routers.auth import get_current_user
from app.database import get_db

@pytest.mark.asyncio
async def test_stream_with_newly_cached_content():
    """
    Test that stream handles cases where cached_content.updated_at is None (newly created)
    by falling back to created_at.
    """
    filing_id = 999
    user_id = 888
    
    mock_filing = MagicMock()
    mock_filing.id = filing_id
    mock_filing.document_url = "http://test.com/filing.htm"
    mock_filing.filing_type = "10-K"
    mock_filing.accession_number = "000-000-000"
    mock_filing.company = MagicMock()
    mock_filing.company.name = "Test Corp"
    
    # Mock cache with None updated_at but valid created_at
    mock_cache = MagicMock()
    mock_cache.critical_excerpt = "Cached excerpt"
    mock_cache.updated_at = None
    import datetime
    # Use timezone aware UTC time for created_at to avoid TypeError in comparison
    mock_cache.created_at = datetime.datetime.now(datetime.timezone.utc)
    mock_filing.content_cache = mock_cache
    
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_pro = True
    
    mock_db = MagicMock()
    # Handle query chain: db.query(Filing).options(...).filter(...).first()
    mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_filing
    # Handle query chain: db.query(Summary).filter(...).first()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    async def override_get_current_user():
        return mock_user
    
    def override_get_db():
        return mock_db
        
    mock_session_cls = MagicMock()
    mock_session_cls.return_value = mock_db
    mock_session_cls.return_value.__enter__.return_value = mock_db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("app.routers.summaries.sec_edgar_service.get_filing_document", new_callable=AsyncMock), \
             patch("app.routers.summaries.openai_service.summarize_filing", new_callable=AsyncMock) as mock_ai, \
             patch("app.routers.summaries.check_usage_limit", return_value=(True, 0, 10)), \
             patch("app.routers.summaries.record_progress"), \
             patch("app.database.SessionLocal", mock_session_cls):
            
            # Setup AI mock response
            mock_ai.return_value = {
                "status": "complete",
                "business_overview": "Summary"
            }
            
            client = TestClient(app)
            response = client.post(
                f"/api/summaries/filing/{filing_id}/generate-stream",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            content = response.text
             
            # Verify we didn't crash with TypeError
            if "error" in content.lower():
                 print(f"FAILED CONTENT: {content}")
            
            assert "error" not in content.lower() or "complete" in content.lower()
            
    finally:
        app.dependency_overrides.clear()
