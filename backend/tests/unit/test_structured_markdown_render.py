"""Wave V visual-appeal guard: the deterministic markdown renderer bolds key figures.

`_build_structured_markdown` is the live user-facing renderer (the LLM editorial writer is
disabled — decision 3a) and its output is what the eval scores via `business_overview`. These
tests lock in that the financials bullets bold the metric label + current value (scannability)
WITHOUT bolding "Not disclosed" placeholders, and that the bold markup stays substring-matchable
so the eval numeric scorers are unaffected.
"""
import pytest

from app.services.openai_service import openai_service


def _summary():
    return {
        "metadata": {"company_name": "TestCo", "filing_type": "10-K", "reporting_period": "FY2025"},
        "sections": {
            "executive_snapshot": {"headline": "TestCo grew.", "key_points": ["Revenue up"], "tone": "neutral"},
            "financial_highlights": {
                "table": [
                    {"metric": "Revenue", "current_period": "$42.3B", "prior_period": "$37.1B",
                     "change": "+14%", "commentary": "driven by services"},
                    {"metric": "EPS (Diluted)", "current_period": "Not disclosed"},
                ],
                "cash_flow": ["Operating cash flow $12.7B; capex $3.0B; free cash flow $9.7B"],
                "balance_sheet": ["Current assets $30.6B, current liabilities $24.3B, current ratio 1.26x"],
            },
        },
    }


def test_financials_bullet_bolds_metric_and_current_value():
    md = openai_service._build_structured_markdown(_summary())
    # Metric label and the real current figure are both bolded.
    assert "- **Revenue:** **$42.3B**" in md
    # Prior period / change are NOT bolded (kept secondary, so the current figure stands out).
    assert "vs. $37.1B (+14%)" in md


def test_not_disclosed_placeholder_is_not_bolded():
    md = openai_service._build_structured_markdown(_summary())
    assert "- **EPS (Diluted):** Not disclosed" in md
    assert "**Not disclosed**" not in md


def test_bolded_figures_remain_substring_matchable_for_eval_scorers():
    # The eval's numeric scorers do a plain substring match on a lowercased haystack; the bold
    # asterisks must not separate the digits from their renderings ("42.3" still present).
    md = openai_service._build_structured_markdown(_summary()).lower()
    assert "42.3" in md
    assert "12.7" in md  # cash-flow figure still rendered
    assert "30.6" in md  # working-capital figure still rendered
