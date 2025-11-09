import asyncio
import importlib
import sys
import types


def _load_openai_service():
    if 'openai' not in sys.modules:
        stub = types.ModuleType('openai')

        class _AsyncOpenAI:
            def __init__(self, *args, **kwargs):
                pass

        stub.AsyncOpenAI = _AsyncOpenAI
        stub.OpenAI = _AsyncOpenAI
        sys.modules['openai'] = stub

    if 'app' not in sys.modules:
        sys.modules['app'] = types.ModuleType('app')

    if 'app.config' not in sys.modules:
        config_module = types.ModuleType('app.config')

        class _Settings:
            OPENAI_API_KEY = 'test-key'
            OPENAI_BASE_URL = None

        config_module.settings = _Settings()
        sys.modules['app.config'] = config_module
        setattr(sys.modules['app'], 'config', config_module)

    module = importlib.import_module('backend.app.services.openai_service')
    return module.OpenAIService


def test_summarize_filing_populates_remediation_sections(monkeypatch):
    OpenAIService = _load_openai_service()
    service = OpenAIService()

    async def fake_generate_structured_summary(*args, **kwargs):
        payload = {
            "sections": {
                "executive_snapshot": None,
                "financial_highlights": {},
                "risk_factors": [],
                "management_discussion_insights": None,
                "segment_performance": [],
                "liquidity_capital_structure": None,
                "guidance_outlook": None,
                "notable_footnotes": [],
            },
            "metadata": {
                "company_name": "Example Corp",
                "filing_type": "10-Q",
                "reporting_period": "Q1 2024",
            },
        }
        service._apply_structured_fallbacks(
            payload["sections"],
            payload["metadata"],
            kwargs.get("xbrl_metrics"),
        )
        return payload

    async def fake_generate_editorial_markdown(structured_summary):
        return {"markdown": "Overview"}

    monkeypatch.setattr(service, "generate_structured_summary", fake_generate_structured_summary)
    monkeypatch.setattr(service, "generate_editorial_markdown", fake_generate_editorial_markdown)

    xbrl_metrics = {
        "revenue": {
            "current": {"value": 1_200_000_000, "period": "Q1 2024"},
            "prior": {"value": 1_050_000_000, "period": "Q1 2023"},
        }
    }

    summary = asyncio.run(
        service.summarize_filing(
            filing_text="Sample filing text",
            company_name="Example Corp",
            filing_type="10-Q",
            previous_filings=None,
            xbrl_metrics=xbrl_metrics,
            filing_excerpt=None,
        )
    )

    raw_sections = summary["raw_summary"]["sections"]

    assert summary["key_changes"].strip(), "Guidance remediation should provide key changes text"
    assert raw_sections["guidance_outlook"]["guidance"].strip()
    assert raw_sections["guidance_outlook"]["watch_items"], "Expected watch items bullet"

    assert raw_sections["liquidity_capital_structure"]["liquidity"].strip()
    assert raw_sections["liquidity_capital_structure"]["shareholder_returns"], "Expected shareholder returns bullet"

    footnotes = raw_sections["notable_footnotes"]
    assert isinstance(footnotes, list) and footnotes, "Footnotes remediation should add an item"
    assert footnotes[0]["item"].strip()
