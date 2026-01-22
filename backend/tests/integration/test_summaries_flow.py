import pytest
from unittest.mock import MagicMock, AsyncMock, patch, ANY
from app.services.summary_generation_service import generate_summary_background
from app.models import Filing, Summary, SummaryGenerationProgress, User, FilingContentCache
from datetime import datetime

@pytest.mark.asyncio
async def test_generate_summary_background_success():
    """
    Test the happy path of _generate_summary_background.
    Verifies that:
    1. Filing is fetched
    2. Progress is updated
    3. OpenAI service is called
    4. Summary is saved to DB
    """
    filing_id = 123
    user_id = 456
    
    # Mock DB Session
    mock_db = MagicMock()
    # Context manager support for SessionLocal()
    mock_session_cls = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_db
    
    # Mock Data Objects
    mock_filing = Filing(
        id=filing_id,
        company_id=1,
        filing_type="10-K",
        document_url="http://sec.gov/doc.htm",
        accession_number="000-000-000",
        filing_date=datetime.now(),
        content_cache=FilingContentCache(critical_excerpt="excerpt")
    )
    mock_filing.company = MagicMock()
    mock_filing.company.name = "Test Corp"
    mock_filing.company.cik = "1234567890"

    mock_user = User(id=user_id, is_pro=True)
    
    # Setup DB Query Returns
    # First query gets Filing
    # Second query checks for existing Summary (None)
    # Queries for User
    # Queries for Progress
    def query_side_effect(model_cls):
        mock_query = MagicMock()
        if model_cls == Filing:
            mock_query.options.return_value.filter.return_value.first.return_value = mock_filing
        elif model_cls == Summary:
            mock_query.filter.return_value.first.return_value = None
        elif model_cls == User:
            mock_query.filter.return_value.first.return_value = mock_user
        elif model_cls == SummaryGenerationProgress:
            mock_query.filter.return_value.first.return_value = SummaryGenerationProgress()
        return mock_query

    mock_db.query.side_effect = query_side_effect

    # Mock Services
    with patch("app.services.summary_generation_service.SessionLocal", mock_session_cls), \
         patch("app.services.summary_generation_service.sec_edgar_service") as mock_sec, \
         patch("app.services.summary_generation_service.openai_service") as mock_openai, \
         patch("app.services.summary_generation_service.xbrl_service") as mock_xbrl, \
         patch("app.services.summary_generation_service.settings") as mock_settings:
        
        # Configure Mocks
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_sec.get_filing_document = AsyncMock(return_value="Filing Text Content")
        mock_openai.extract_critical_sections = MagicMock(return_value="Critical Excerpt")
        mock_xbrl.get_xbrl_data = AsyncMock(return_value=None) # Skip XBRL for simplicity
        
        # Mock OpenAI Response
        mock_summary_data = {
            "status": "complete",
            "business_overview": "Overview text",
            "financial_highlights": {"revenue": "1B"},
            "risk_factors": [{"summary": "Risk 1", "supporting_evidence": "Evidence 1"}],
            "management_discussion": "MD&A text",
            "key_changes": "Changes text",
            "raw_summary": {
                "sections": {"financial_highlights": {}},
                "section_coverage": {"covered_count": 5, "total_count": 5}
            }
        }
        mock_openai.summarize_filing = AsyncMock(return_value=mock_summary_data)

        # Execute
        await generate_summary_background(filing_id, user_id)

        # Assertions
        # 1. Check filing was fetched
        mock_sec.get_filing_document.assert_called_with("http://sec.gov/doc.htm", timeout=ANY)
        
        # 2. Check OpenAI called
        mock_openai.summarize_filing.assert_called()
        
        # 3. Check Summary Saved
        # db.add is called for progress, maybe cache, and finally Summary
        added_instances = [args[0] for name, args, kwargs in mock_db.add.mock_calls]
        summary_saved = next((obj for obj in added_instances if isinstance(obj, Summary)), None)
        assert summary_saved is not None
        assert summary_saved.business_overview == "Overview text"
        assert summary_saved.filing_id == filing_id
        
        # 4. Check Commit
        assert mock_db.commit.called
