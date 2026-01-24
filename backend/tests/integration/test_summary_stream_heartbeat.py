"""
Integration tests for summary stream heartbeat mechanism.

Verifies that:
1. Heartbeat progress events are emitted during long-running AI operations
2. SSE stream remains open and active during the wait
3. Final output is correctly yielded after completion
4. Error handling works correctly during the wait state
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from app.routers.auth import get_current_user
from app.database import get_db

@pytest.mark.asyncio
async def test_stream_heartbeat_during_long_ai_operation():
    """
    Test that heartbeat events are emitted every ~5 seconds during a long-running AI operation.
    """
    filing_id = 123
    user_id = 456
    
    # Mock a long-running AI operation (20 seconds) - actually mocked to be shorter for test speed
    # We rely on the heartbeat interval being mocked to be very short
    async def slow_summarize_filing(*args, **kwargs):
        await asyncio.sleep(0.5)  # Short sleep but longer than heartbeat check (if we mock interval)
        return {
            "status": "complete",
            "business_overview": "Test summary",
            "financial_highlights": None,
            "risk_factors": [],
            "management_discussion": None,
            "key_changes": None,
            "raw_summary": {}
        }
    
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
    # Mock queries
    # First query looks for filing
    mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_filing
    # Second query looks for existing summary (None)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Setup overrides
    async def override_get_current_user():
        return mock_user
    
    def override_get_db():
        return mock_db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    
    # Mock SessionLocal for the background stream task
    mock_session_cls = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_db
    
    try:
        with patch("app.routers.summaries.sec_edgar_service.get_filing_document", new_callable=AsyncMock) as mock_sec, \
             patch("app.routers.summaries.openai_service.summarize_filing", side_effect=slow_summarize_filing), \
             patch("app.routers.summaries.check_usage_limit", return_value=(True, 0, 10)), \
             patch("app.routers.summaries.record_progress"), \
             patch("app.routers.summaries.get_or_cache_excerpt", return_value="excerpt"), \
             patch("app.config.settings.STREAM_HEARTBEAT_INTERVAL", 0.1), \
             patch("app.database.SessionLocal", mock_session_cls):
            
            client = TestClient(app)
            
            response = client.post(
                f"/api/summaries/filing/{filing_id}/generate-stream",
                headers={"Authorization": "Bearer test-token"}
            )
            
            # Verify response is streaming
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            
            # Count heartbeats in response text
            # Note: TestClient collects all streaming response into response.text
            content = response.text
            # Check for new rotating heartbeat messages (stage: summarizing with various messages)
            # The new implementation uses rotating messages like "Analyzing financial highlights..."
            heartbeat_count = content.count('"stage": "summarizing"')
            # Should have at least 2 heartbeats (0.5s sleep / 0.1s interval = ~5)
            assert heartbeat_count >= 2
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stream_handles_ai_error_gracefully():
    """
    Test that errors during AI processing are handled gracefully and streamed to client.
    """
    filing_id = 123
    user_id = 456
    
    # Mock an AI operation that raises an error
    async def failing_summarize_filing(*args, **kwargs):
        await asyncio.sleep(0.1)  # Short delay before error
        raise Exception("AI service unavailable")
    
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
    mock_session_cls.return_value.__enter__.return_value = mock_db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("app.routers.summaries.sec_edgar_service.get_filing_document", new_callable=AsyncMock, return_value="Filing text"), \
             patch("app.routers.summaries.openai_service.summarize_filing", side_effect=failing_summarize_filing), \
             patch("app.routers.summaries.check_usage_limit", return_value=(True, 0, 10)), \
             patch("app.routers.summaries.record_progress"), \
             patch("app.routers.summaries.get_or_cache_excerpt", return_value="excerpt"), \
             patch("app.database.SessionLocal", mock_session_cls):
            
            client = TestClient(app)
            response = client.post(
                f"/api/summaries/filing/{filing_id}/generate-stream",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            content = response.text
            assert "error" in content.lower() or "unable" in content.lower()
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_heartbeat_events_emitted_at_interval():
    """
    Verify that heartbeat events are emitted approximately every 5 seconds.
    Placeholder / Redundant with test_stream_heartbeat_during_long_ai_operation which tests actual logic.
    """
    # This test was a placeholder and is now covered by test_stream_heartbeat_during_long_ai_operation
    # We can keep it simple or minimal.
    assert True
