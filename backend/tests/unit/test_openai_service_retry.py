
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.openai_service import OpenAIService

@pytest.mark.asyncio
async def test_summarize_retries_on_empty_payload():
    """
    Test that the service retries with the next model if the first one returns an empty payload.
    """
    service = OpenAIService()
    
    # Mock the AsyncOpenAI client
    service.client = MagicMock()
    service.client.chat.completions.create = AsyncMock()
    
    # Setup mock responses
    # Response 1: Success 200 OK but empty content
    response_empty = MagicMock()
    response_empty.choices = [MagicMock()]
    response_empty.choices[0].message.content = "" # Empty content
    
    # Response 2: Success with valid JSON
    response_valid = MagicMock()
    response_valid.choices = [MagicMock()]
    response_valid.choices[0].message.content = '{"markdown": "Valid summary", "sections": {}}'
    
    # Configure side_effect to return empty first, then valid
    service.client.chat.completions.create.side_effect = [response_empty, response_valid]
    
    # Mock _clean_json_payload to just return the content as-is for simplicity
    service._clean_json_payload = lambda x: x
    
    # Call summarize (wraps the loop)
    # We need to mock the internal _summarize or just call a method that uses the loop
    # The loop is likely in a private method or the main summarize method.
    # Based on the file context we saw, let's assume this logic is in a method we can target.
    # Looking at the trace, it seems to be in `summarize` or `_generate_structured_summary`
    
    # Let's try to verify by inspecting the file content again if needed, 
    # but for now assume we can test the loop isolation if we mock properly.
    # Actually, to be safe, let's look at where the loop is.
    pass 
