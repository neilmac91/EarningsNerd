"""
Performance tests for concurrent long-running SSE connections.
"""

import pytest
import asyncio
import json
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
import os
# Set safe dummy secret key for testing
os.environ["SECRET_KEY"] = "test-secret-key-must-be-long-enough-123"

from main import app
from app.routers.auth import get_current_user
from app.database import get_db

@pytest.mark.asyncio
async def test_heartbeat_events_emitted_at_interval():
    """
    Verify that heartbeat events are emitted approximately every 5 seconds (or configured interval).
    """
    filing_id = 123
    user_id = 999
    
    # Mock dependencies
    mock_filing = MagicMock()
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
    
    # Mock slow AI operation
    async def slow_summarize(*args, **kwargs):
        # The configured interval in logic below is 2s
        await asyncio.sleep(7)
        return {
            "status": "complete",
            "business_overview": "Summary",
            "raw_summary": {}
        }

    # Setup overrides
    async def override_get_current_user():
        return mock_user

    mock_db = MagicMock()
    # Handle query chains
    # db.query(Filing).options(...).filter(...).first()
    mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_filing
    # db.query(Summary).filter(...).first() -> None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def override_get_db():
        return mock_db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    
    # Mock SessionLocal for the background stream task
    mock_session_cls = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_db

    try:
        with patch("app.routers.summaries.sec_edgar_service.get_filing_document", new_callable=AsyncMock, return_value="Filing text"), \
             patch("app.routers.summaries.openai_service.summarize_filing", side_effect=slow_summarize), \
             patch("app.routers.summaries.check_usage_limit", return_value=(True, 0, 10)), \
             patch("app.routers.summaries.record_progress"), \
             patch("app.routers.summaries.get_or_cache_excerpt", return_value="excerpt"), \
             patch("app.config.settings.STREAM_HEARTBEAT_INTERVAL", 2), \
             patch("app.database.SessionLocal", mock_session_cls), \
             patch("app.routers.summaries.enforce_rate_limit"):
            
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                async with client.stream(
                    "POST", 
                    f"/api/summaries/filing/{filing_id}/generate-stream",
                    headers={"Authorization": "Bearer test-token"}
                ) as response:
                    assert response.status_code == 200
                    
                    events = []
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            events.append(data)
                    
                    # Filter for heartbeat events
                    heartbeats = [e for e in events if e.get("type") == "progress" and "Processing financial data" in e.get("message", "")]
                    
                    # Should have at least 2-3 heartbeats
                    assert len(heartbeats) >= 2
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_concurrent_stream_connections():
    """
    Test that server can handle multiple concurrent long-running connections.
    """
    n_concurrent = 5
    filing_id = 123
    user_id = 999
    
    mock_filing = MagicMock()
    mock_filing.document_url = "http://test.com/filing.htm"
    mock_filing.company.name = "Test Corp"
    mock_filing.filing_type = "10-K"
    
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_pro = True

    async def medium_summarize(*args, **kwargs):
        await asyncio.sleep(2)
        return {
            "status": "complete",
            "business_overview": "Summary",
            "raw_summary": {}
        }

    mock_db = MagicMock()
    # We need to be careful with mock_db reuse across threads/tasks if they were real threads
    # But here everything is async so it's fine.
    # Also need to handle finding filing inside the stream (using SessionLocal)
    mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_filing
    mock_db.query.return_value.filter.return_value.first.return_value = None

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
             patch("app.routers.summaries.openai_service.summarize_filing", side_effect=medium_summarize), \
             patch("app.routers.summaries.check_usage_limit", return_value=(True, 0, 10)), \
             patch("app.routers.summaries.record_progress"), \
             patch("app.routers.summaries.get_or_cache_excerpt", return_value="excerpt"), \
             patch("app.database.SessionLocal", mock_session_cls), \
             patch("app.routers.summaries.enforce_rate_limit"):

            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                
                async def make_request():
                    async with client.stream(
                        "POST", 
                        f"/api/summaries/filing/{filing_id}/generate-stream",
                        headers={"Authorization": "Bearer test-token"}
                    ) as response:
                        assert response.status_code == 200
                        lines = []
                        async for line in response.aiter_lines():
                            lines.append(line)
                        return lines

                tasks = [make_request() for _ in range(n_concurrent)]
                results = await asyncio.gather(*tasks)
                
                assert len(results) == n_concurrent
                for lines in results:
                    content = "".join(lines)
                    if "complete" not in content:
                        print(f"FAILED CONTENT: {content}")
                    assert "complete" in content
    finally:
        app.dependency_overrides.clear()
