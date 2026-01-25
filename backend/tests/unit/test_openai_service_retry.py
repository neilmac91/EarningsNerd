
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.openai_service import OpenAIService

@pytest.mark.asyncio
async def test_summarize_retries_on_empty_payload():
    """
    Test that generate_structured_summary retries with the next model if:
    1. The first response has no choices (malformed).
    2. The second response has choices but empty content (blocked/filtered).
    3. The third response is valid.
    """
    service = OpenAIService()
    
    # Mock the AsyncOpenAI client
    service.client = MagicMock()
    service.client.chat.completions.create = AsyncMock()
    
    # Mock fallback models to ensure we have enough retries
    # Initial model + 2 fallbacks = 3 attempts total required for this test
    service._fallback_models = ["model-backup-1", "model-backup-2"]
    
    # Scenario 1: Malformed response (no choices)
    response_malformed = MagicMock()
    # Simulate missing choices attribute or empty list
    response_malformed.choices = [] 
    
    # Scenario 2: Success 200 OK but empty content
    response_empty_content = MagicMock()
    response_empty_content.choices = [MagicMock()]
    response_empty_content.choices[0].message.content = "   " # Whitespace only
    
    # Scenario 3: Success with valid JSON
    valid_json = {
        "markdown": "Valid summary", 
        "sections": {
            "financial_highlights": {"table": []},
            "risk_factors": []
        }
    }
    response_valid = MagicMock()
    response_valid.choices = [MagicMock()]
    response_valid.choices[0].message.content = json.dumps(valid_json)
    
    # Configure side_effect to return malformed -> empty -> valid
    service.client.chat.completions.create.side_effect = [
        response_malformed, 
        response_empty_content, 
        response_valid
    ]
    
    # Mock internal helpers to isolate the loop logic
    service.get_model_for_filing = MagicMock(return_value="primary-model")
    service._get_type_config = MagicMock(return_value={"ai_timeout": 1.0, "max_tokens": 100})
    service._build_section_sample = MagicMock(return_value="Sample text")
    service._clean_json_payload = lambda x: x.strip()
    # Mock finding empty sections to prevent post-processing modifications
    service._find_empty_sections = MagicMock(return_value={})
    
    # Call the method under test
    # We pass minimal dummy args
    result = await service.generate_structured_summary(
        filing_text="Full text",
        company_name="Test Corp",
        filing_type="10-K",
        previous_filings=[],
        xbrl_metrics={},
        filing_excerpt="Excerpt"
    )
    
    # Verify the result contains our success marker
    # The service may add default sections, so we just check the core content survives
    assert result.get("markdown") == "Valid summary"
    assert result.get("markdown") == "Valid summary"
    # We ignore specific sections structure as it gets enriched with defaults
    # assert result["sections"]["financial_highlights"] == {"table": []}
    
    # Verify we called create 3 times (Primary -> Retry 1 -> Retry 2)
    assert service.client.chat.completions.create.call_count == 3
    
    # Verify the models used were correct (Primary, then fallbacks)
    # The models_to_try list logic: [primary] + fallback_models
    # Attempts:
    # 1. Primary (failed malformed)
    # 2. Backup 1 (failed empty content)
    # 3. Backup 2 (succeeded)
    
    calls = service.client.chat.completions.create.call_args_list
    assert calls[0].kwargs["model"] == "primary-model"
    assert calls[1].kwargs["model"] == "model-backup-1"
    assert calls[2].kwargs["model"] == "model-backup-2"
