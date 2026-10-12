"""``is_summary_ready``: whether the filing page shows a stored summary's body.

The rule the page's display and metadata, the sitemap and the company search apply (the frontend
mirrors it in features/summaries/lib/summaryPlaceholder.ts, held equal by summaryPlaceholder.spec).
"""
import pytest

from app.services.summary_placeholders import IN_PROGRESS_MARKER, SUMMARY_FAILURE_TOKENS, is_summary_ready


def test_failure_tokens_are_the_placeholder_tokens_but_the_in_progress_one():
    assert IN_PROGRESS_MARKER == "Generating summary"
    assert SUMMARY_FAILURE_TOKENS == ("summary temporarily unavailable", "requires openai api key")


@pytest.mark.parametrize(
    ("overview", "writer_error", "ready"),
    [
        ("Apple designs devices.", None, True),
        # Prose that mentions the phrase is content: the marker is matched case-sensitively.
        ("A real partial overview about generating summary reports.", None, True),
        ("Generating summary...", None, False),
        ("Please wait: Generating summary…", None, False),
        ("## Executive Summary\n\nSummary temporarily unavailable. Please retry.", None, False),
        ("Summary generation requires OpenAI API key. Please configure OPENAI_API_KEY in your .env file.", None, False),
        ("Apple designs devices.", "timeout", False),
        ("   ", None, False),
        (None, None, False),
    ],
)
def test_ready_means_the_filing_page_shows_the_body(overview, writer_error, ready):
    assert is_summary_ready(overview, writer_error) is ready
