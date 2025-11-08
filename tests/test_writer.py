import pathlib

from backend.pipeline.extract import extract_ixbrl_metrics
from backend.pipeline.validate import validate_summary
from backend.pipeline.write import generate_markdown
from backend.pipeline.quality import ensure_quality

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "aapl-20250329.htm"


def test_writer_generates_markdown_without_empty_sections():
    html = FIXTURE.read_text()
    summary = extract_ixbrl_metrics(
        html,
        cik="0000320193",
        symbol="AAPL",
        company_name="Apple Inc.",
        filing_type="10-Q",
        filing_date="2025-05-02",
        period_end="2025-03-29",
    )
    validated, meta = validate_summary(summary)
    markdown = generate_markdown(validated, meta)
    clean_markdown, scores = ensure_quality(markdown)

    assert "Not disclosed" not in clean_markdown
    assert all(section.strip() for section in clean_markdown.split("##") if section)
    words = [word for word in clean_markdown.replace("##", "").split() if word]
    assert 200 <= len(words) <= 320
    assert sum(scores.values()) >= 28
