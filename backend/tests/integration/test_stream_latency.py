
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from app.routers.auth import get_current_user
from app.database import get_db

@pytest.mark.asyncio
async def test_stream_handles_high_latency_fetch():
    """
    Test that the stream emits heartbeat events during a high-latency SEC fetch operation.
    This simulates the 'hanging' scenario and verifies our fix keeps the connection alive.
    """
    filing_id = 123
    user_id = 456
    
    # Mock a slow SEC fetch (3 seconds)
    # The heartbeat interval is mocked to 0.5s, so we expect ~5-6 heartbeats
    async def slow_fetch(*args, **kwargs):
        await asyncio.sleep(2.0)
        return "Filing text content"
    
    # Mock database and services
    mock_filing = MagicMock()
    mock_filing.id = filing_id
    mock_filing.document_url = "http://test.com/filing.htm"
    mock_filing.filing_type = "10-K"
    mock_filing.accession_number = "000-000-000"
    mock_filing.company = MagicMock()
    mock_filing.company.name = "Test Corp"
    mock_filing.company.cik = "1234567890"
    mock_filing.content_cache = None
    
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_pro = True

    mock_db = MagicMock()
    mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_filing
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Setup overrides
    async def override_get_current_user():
        return mock_user
    
    def override_get_db():
        return mock_db
    
    # Mock SessionLocal for the background stream task
    mock_session_cls = MagicMock()
    mock_session_cls.return_value = mock_db
    mock_session_cls.return_value.__enter__.return_value = mock_db 
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        with patch("app.routers.summaries.sec_edgar_service.get_filing_document", side_effect=slow_fetch), \
             patch("app.routers.summaries.openai_service.summarize_filing", return_value={"status": "complete", "business_overview": "Summary"}), \
             patch("app.routers.summaries.check_usage_limit", return_value=(True, 0, 10)), \
             patch("app.routers.summaries.record_progress"), \
             patch("app.routers.summaries.get_or_cache_excerpt", return_value="excerpt"), \
             patch("app.config.settings.STREAM_HEARTBEAT_INTERVAL", 0.3), \
             patch("app.database.SessionLocal", mock_session_cls), \
             patch("app.routers.summaries.xbrl_service.get_xbrl_data", new_callable=AsyncMock, return_value=None):
            
            client = TestClient(app)
            
            response = client.post(
                f"/api/summaries/filing/{filing_id}/generate-stream",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            content = response.text
            
            # Check for fetch heartbeats
            # We expect multiple "Connecting to SEC EDGAR..." or similar messages
            heartbeats = [line for line in content.split('\n') if 'Connecting to SEC EDGAR' in line or 'Downloading filing document' in line]
            
            # With 2s sleep and 0.3s interval, we should have at least 3-4 heartbeats
            assert len(heartbeats) >= 2, f"Expected heartbeats, got count: {len(heartbeats)}"
            
            # Ensure final completion
            assert "complete" in content
            
    finally:
        app.dependency_overrides.clear()
